"""
tui interface for network connections using NetworkManager and the bones of the
newm-panel lock class. This launcher consists of 3 menus:
    List Devices == List network devices
    Scan Networks == Connect to wireless networks after a scan
    Connection Status == Check current connection status
"""
from __future__ import annotations
from typing import Any, Dict, List
from pyfiglet import Figlet
import curses
import time
import logging
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

    def get_connection_status(self) -> List[str]:
        """Get current connection status using NM Client"""
        status = []
        if not self.client:
            return ["NetworkManager is not available"]

        try:
            # get active connections
            active_connections = self.client.get_active_connections()

            if active_connections:
                status.append("active_connections:")
                for conn in active_connections:
                    conn_id = conn.get_id()
                    conn_type = conn.get_connection_type()
                    devices = conn.get_devices()
                    device_names = [d.get_iface() for d in devices] if devices else ["unknown"]
                    status.append("\n")
                    status.append(f"    {conn_id} ({conn_type}) on {', '.join(device_names)}")
            else:
                status.append("\nNo active connections")

            # get IP addresses from devices
            status.append("")
            status.append("Device Status:")
            for device in self.client.get_devices():
                if device.get_state() == NM.DeviceState.ACTIVATED:
                    iface = device.get_iface()

                    ip4_config = device.get_ip4_config()
                    if ip4_config:
                        addresses = ip4_config.get_addresses()
                        if addresses:
                            addr = addresses[0].get_address()
                            prefix = addresses[0].get_prefix()
                            status.append(f"    {iface}: {addr}/{prefix}")

                    ip6_config = device.get_ip6_config()
                    if ip6_config:
                        addresses = ip6_config.get_addresses()
                        for addr_obj in addresses:
                            addr = addr_obj.get_address()
                            prefix = addr_obj.get_prefix()
                            # only show global addresses
                            if not addr.startswith('fe80'):
                                status.append(f"    {iface}: {addr}/{prefix}")
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            status.append(f"Error: {e}")

        return status if status else ["No connection information available"]

    def connect_to_network(self, ssid: str, password: str = "") -> bool:
        """Connect to network using NM Client"""
        if not self.client:
            return False

        try:
            wifi_devices = [d for d in self.client.get_devices() if d.get_device_type() == NM.DeviceType.WIFI]
            if not wifi_devices:
                return False

            wifi_device = wifi_devices[0]

            # Find the access point
            target_ap = None
            for network in self.networks:
                if network['ssid'] == ssid:
                    target_ap = network['ap']
                    break

            if not target_ap:
                return False

            # Create a new connection
            connection = NM.SimpleConnection.new()
            # establish settings
            # -> Connection Settings
            s_conn = NM.SettingConnection.new()
            s_conn.set_property("type", "802-11-wireless")
            s_conn.set_property("id", ssid)
            connection.add_setting(s_conn)
            # -> Wireless settings
            s_wifi = NM.SettingWireless.new()
            s_wifi.set_property("ssid", target_ap.get_ssid())
            connection.add_setting(s_wifi)
            # -> Security settings if password provided
            if password:
                s_wifi_sec = NM.SettingWirelessSecurity.new()
                s_wifi_sec.set_property("key-mgmt", "wpa-psk")
                s_wifi_sec.set_property("psk", password)
                connection.add_setting(s_wifi_sec)

            # add and activate connection asychronously
            self.client.add_and_activate_connection(
                connection,
                wifi_device,
                target_ap.get_path(),
                None
            )

            # wait for connection to establish
            time.sleep(3)

            # check for network connection
            if wifi_device.get_state() == NM.DeviceState.ACTIVATED:
                return True

        except Exception as e:
            logger.error(f"Failed to connect to {ssid}: {e}")
        return False

    def disconnect_all(self) -> None:
        """Disconnect from all connections using NM Client"""
        if not self.client:
            return

        try:
            active_connections = self.client.get_active_connections()
            for conn in active_connections:
                try:
                    self.client.deactivate_connection(conn, None)
                except Exception as e:
                    logger.warning(f"Failed to deactivate {conn.get_id()}: {e}")
        except Exception as e:
            logger.error(f"Failed to disconnect: {e}")

    def main_menu_router(self) -> None:
        """Handle main menu input"""
        while True:
            self.render()
            ch = self.scr.getch()

            if ch == curses.ERR or ch == 410:
                continue
            elif ch == curses.KEY_BACKSPACE:
                self.search = self.search[:-1] if len(self.search) > 0 else ""
            elif ch == 10:  # enter
                break
            elif ch == 27:  # escape
                return
            else:
                try:
                    sch = chr(ch)
                    self.search += sch
                except:
                    logger.exception("main_menu input")

            if self.search in ['1', '2', '3', '4', 'q']:
                break

        if self.search == '1':  # list devices
            self.state = "device_list"
            self.devices = self.get_devices()
            self.selected_idx = 0
        elif self.search == '2':  # scan networks
            self.state = "network_list"
            self.pending = True
            self.render()
            self.networks = self.scan_networks()
            self.pending = False
            self.selected_idx = 0
        elif self.search == '3':  # connection status
            self.state = "connection_status"
        elif self.search == '4':
            self.message = "Disconnecting ...."
            self.render()
            self.disconnect_all()
            time.sleep(2)
            self.state = "main_menu"
        elif self.search == 'q':
            return

        self.search = ""

    def device_list_router(self) -> None:
        """Handle device list navigation"""
        while True:
            self.render()
            ch = self.scr.getch()
            if ch == 27:  # escape
                self.state = "main_menu"
                break
            elif ch == curses.KEY_UP and self.devices:
                self.selected_idx = (self.selected_idx - 1) % len(self.devices)
            elif ch == curses.KEY_DOWN and self.devices:
                self.selected_idx = (self.selected_idx + 1) % len(self.devices)

    def network_list_router(self) -> None:
        while True:
            self.render()
            ch = self.scr.getch()

            if ch == 27:  # escape
                self.state = "main_menu"
                break
            elif ch == curses.KEY_UP and self.networks:
                self.selected_idx = (self.selected_idx - 1) % len(self.networks)
            elif ch == curses.KEY_DOWN and self.networks:
                self.selected_idx = (self.selected_idx + 1) % len(self.networks)
            elif ch == 10 and self.networks:  # enter
                selected_network = self.networks[self.selected_idx]
                self.state = "password_input"
                self.message = f"Password for {selected_network['ssid']}:"
                self.password = ""
                self.enter_password()

                if self.password:  # user didn't cancel
                    self.pending = True
                    self.render()
                    success = self.connect_to_network(
                        selected_network['ssid'], self.password
                    )
                    self.pending = False
                    self.message = "Connected!" if success else "Failed to connect"
                    self.render()
                    time.sleep(2)

                self.state = "network_list"
                self.password = ""
            else:
                # open network
                self.pending = True
                self.render()
                success = self.connect_to_network(selected_network['ssid'])
                self.pending = False
                self.message = "Connected!" if success else "Failed to connect"
                self.render()
                time.sleep(2)

    def connection_status_router(self) -> None:
        while True:
            self.render()
            ch = self.scr.getch()

            if ch == 27:  # escape
                self.state = "main_menu"
                break

    def enter_password(self) -> None:
        while True:
            self.render()
            ch = self.ch.getch()

            if ch == curses.ERR or ch == 410:
                continue
            elif ch == curses.KEY_BACKSPACE:
                self.password = self.password[:-1] if len(self.password) > 0 else ""
            elif ch == 10:  # enter
                break
            elif ch == 27:  # escape
                self.password = ""
                break
            else:
                try:
                    sch = chr(ch)
                    self.password += sch
                except:
                    logger.exception("enter_password")

    def run(self) -> None:
        """Main run loop"""
        while True:
            if self.state == "main_menu":
                self.main_menu_router()
                if self.search == 'q':
                    break
            elif self.state == "device_list":
                self.device_list_router()
            elif self.state == "network_list":
                self.network_list_router()
            elif self.state == "connection_status":
                self.connection_status_router()


def network_manager() -> None:
    """Main entry point"""
    nm = NetworkLauncher()
    try:
        nm.run()
    finally:
        nm.exit()


def main() -> None:
    while True:
        try:
            network_manager()
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.exception(f"Exception in network manager: {e}")
            time.sleep(0.5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()

    # TODO:
    # [*] create device list functionality
    # [*] create scanning functionality
    # [*] connection status functionality
    # [*] connection to network functionality
    # [*] maybe disconnection from all network functionality
    # [*] routing functionality
    # [*] password input for wifi functionality
