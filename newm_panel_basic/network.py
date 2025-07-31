"""
tui interface for network connections using NetworkManager and the bones of the
newm-panel lock class. This launcher consists of 3 menus:
    List Devices == List network devices
    Scan Networks == Connect to wireless networks after a scan
    Connection Status == Check current connection status
"""
from __future__ import annotations
from typing import Any, Optional, Dict, List, Tuple
from pyfiglet import Figlet
import os
import curses
import json
import time
import logging
import subprocess
import re
import gi
gi.require_version("NM", "1.0")
from gi.repository import GLib, NM

logger = logging.getLogger(__name__)


class NetworkLauncher:
    def __init__(self) -> None:
        self.state = "main_menu"
        self.selected_idx = 0
        self.devices: List[Dict[str, Any]] = []
        self.networks: List[Dict[str, Any]] = []
        self.search = ""
        self.password = ""
        self.message = ""
        self.pending = False
        self.scr = curses.initscr()  # initialize screen
        curses.cbreak()  # enter cbreak mode
        curses.noecho()  # don't echo input characters to stdout
        self.scr.keypad(True)
        curses.curs_set(False)

        # main_menu opts
        self.menu_options = [
            ("1", "List Devices"),
            ("2", "Scan Networks"),
            ("3", "Connection Status"),
            ("q", "Quit")
        ]

        # initialize NetworkManager client
        try:
            self.client = NM.Client.new(None)
        except Exception as e:
            logger.error(f"Failed to connect to NetworkManager: {e}")
            self.client = None

    def exit(self) -> None:
        curses.curs_set(True)
        self.scr.keypad(False)
        curses.echo()
        curses.endwin()

    def render(self) -> None:
        _, width = self.scr.getmaxyx()

        if self.state == "main_menu":
            texts = [
                "",
                "",
                Figlet(font="big", justify="center", width=width)
                .renderText("newm-next"),
                Figlet(font="digital", justify="center", width=width)
                .renderText(
                    "    ".join([f"{k} {v}\n" for k, v in self.menu_options])
                ),
                "    >" + self.search
            ]
        elif self.state == "device_list":
            texts = [
                "",
                "",
                Figlet(font="big", justify="center", width=width)
                .renderText("newm-next"),
                Figlet(font="digital", justify="center", width=width)
                .renderText("Devices"),
                "    [ESC] Back"
            ]
            if self.devices:
                for i, device in enumerate(self.devices):
                    prefix = "    + " if i == self.selected_idx else "      "
                    status = "UP" if device.get('state') == 'activated' \
                        else "DOWN"
                    texts.append(
                        f"{prefix}{device['name']} ({device['type']}) [{status}]"
                    )
            else:
                texts.append("      No devices found...")
        elif self.state == "network_list":
            texts = [
                "",
                "",
                Figlet(font="big", justify="center", width=width)
                .renderText("newm-next"),
                Figlet(font="digital", justify="center", width=width)
                .renderText("Networks"),
                "    [ESC[ Back   [ENTER] Connect"
            ]
            if self.pending:
                texts.append("      Scanning...")
            elif self.networks:
                for i, network in enumerate(self.networks):
                    prefix = "    + " if i == self.selected_idx else "      "
                    security = "SECURED" if network.get("secured") \
                        else "       "
                    signal = " " * (network.get('strength', 0) // 25)
                    texts.append(
                        f"{prefix} {security}  {network['ssid']} {signal}"
                    )
            else:
                texts.append("    No networks found")
        elif self.state == "connection_status":
            texts = [
                "",
                "",
                Figlet(font="big", justify="center", width=width)
                .renderText("newm-next"),
                Figlet(font="digital", justify="center", width=width)
                .renderText("Status"),
                "    [ESC] Back"
            ]
            status_info = self.get_connection_status()  # TODO
            for line in status_info:
                texts.append(f"    {line}")
        elif self.state == "password_input":
            texts = [
                "",
                "",
                Figlet(font="big", justify="center", width=width)
                .renderText("newm-next"),
                Figlet(font="digital", justify="center", width=width)
                .renderText(self.message),
                Figlet(font="small", justify="center", width=width)
                .renderText(
                    "." * len(self.password) if not self.pending
                    else "Connecting..."
                ),
            ]
        self.scr.erase()
        y = 0
        for t in texts:
            text_split = t.split("\n")
            for line in text_split:
                try:
                    self.scr.addstr(y, 0, line)
                except:
                    pass  # handle screen overflow gracefully
                y += 1
        self.scr.refresh()

    # TODO:
    # [ ] create device list functionality
    # [ ] create scanning functionality
    # [ ] connection status functionality
    # [ ] connection to network functionality
    # [ ] maybe disconnection from all network functionality
    # [ ] routing functionality
    # [ ] password input for wifi functionality


