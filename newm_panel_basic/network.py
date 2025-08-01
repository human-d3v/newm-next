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

    def get_devices(self) -> List[Dict[str, Any]]:
        """Get network devices using NM client"""
        devices = []
        if not self.client:
            return devices

        type_map = {
            NM.DeviceType.ETHERNET: "ethernet",
            NM.DeviceType.WIFI: "wifi",
            NM.DeviceType.LOOPBACK: "loopback",
            NM.DeviceType.BRIDGE: "bridge",
            NM.DeviceType.BOND: "bond",
            NM.DeviceType.TEAM: "team",
        }

        state_map = {
            NM.DeviceState.ACTIVATED: "activated",
            NM.DeviceState.DISCONNECTED: "disconnected",
            NM.DeviceState.UNAVAILABLE: "unavailable",
            NM.DeviceState.PREPARE: "prepare",
            NM.DeviceState.CONFIG: "config",
            NM.DeviceState.NEED_AUTH: "need_auth",
            NM.DeviceState.IP_CONFIG: "ip_config",
            NM.DeviceState.SECONDARIES: "secondaries",
            NM.DeviceState.DEACTIVATING: "deactivating",
            NM.DeviceState.FAILED: "failed",
        }
        try:
            for device in self.client.get_devices():
                devices.append({
                    'name': device.get_iface(),
                    'type': type_map.get(device.get_device_type(), "unknown"),
                    'state': state_map.get(device.get_state(), "unknown"),
                    'device': device
                })
        except Exception as e:
            logger.error(f"Failed to get devices: {e}")
        return devices


    def scan_networks(self) -> List[Dict[str, Any]]:
        """Scan for WiFi networks using NM client"""
        networks = []
        if not self.client:
            return networks
        try:
            wifi_devices = [dev for dev in self.client.get_devices() if
                            dev.get_device_type() == NM.DeviceType.WIFI]
            if not wifi_devices:
                return networks

            wifi_device = wifi_devices[0]

            try: 
                wifi_device.request_scan_async(None, None, None)
                # add delay for aync
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Scan request failed: {e}")

            # get access points
            access_points = wifi_device.get_access_points()
            seen_ssids = set()

            for ap in access_points:
                ssid_bytes = ap.get_ssid()
                if not ssid_bytes:
                    continue

                try:
                    ssid = ssid_bytes.get_data().decode('utf-8')
                except:
                    continue

                if ssid in seen_ssids or not ssid.strip():
                    continue

                seen_ssids.add(ssid)

                # check security
                flags = ap.get_flags()
                wpa_flags = ap.get_wpa_flags()
                rsn_flags = ap.get_rsn_flags()

                secured = bool(flags & NM.AccessPointFlags.PRIVACY or 
                               wpa_flags != NM.AccessPointFlags.NONE or 
                               rsn_flags != NM.AccessPointFlags.NONE)

                networks.append({
                    'ssid': ssid,
                    'strength': ap.get_strength(),
                    'secured': secured,
                    'ap': ap
                })

            # sort by signal strength
            networks.sort(key=lambda x: x['strength'], reverse=True)

        except Exception as e:
            logger.error(f"Failed to scan networks: {e}")
        return networks

    # TODO:
    # [*] create device list functionality
    # [*] create scanning functionality
    # [ ] connection status functionality
    # [ ] connection to network functionality
    # [ ] maybe disconnection from all network functionality
    # [ ] routing functionality
    # [ ] password input for wifi functionality


