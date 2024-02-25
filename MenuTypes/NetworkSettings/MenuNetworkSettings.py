import os
import signal

from RotaryMenu import MenuType, RotaryMenu

import time
import re
import subprocess
import asyncio
from pathlib import Path
from configparser import ConfigParser
import traceback
import shutil


class MenuNetworkSettings(MenuType):
    connection_low = (
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b01000
    )

    connection_medium = (
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00100,
        0b01100
    )

    connection_high = (
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00010,
        0b00110,
        0b01110
    )

    connection_full = (
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00001,
        0b00011,
        0b00111,
        0b01111
    )

    lock = (
        0b00000,
        0b01110,
        0b10001,
        0b11111,
        0b11011,
        0b11011,
        0b01110,
        0b00000
    )

    refresh = (
        0b00000,
        0b00110,
        0b11001,
        0b11000,
        0b00011,
        0b10011,
        0b01100,
        0b00000
    )

    def __init__(self, config_file, back_symbol, forward_symbol,
                 path: Path = Path("/run/NetworkManager/system-connections/"),):
        self.config_file = config_file
        self.back_symbol = back_symbol
        self.forward_symbol = forward_symbol
        self.pr_menu = None
        self.path = path
        self.saved_wifis = list()
        self.found_wifis = list()
        self.current_wifis = list()
        self.current_index = 0
        self.current_connection = str()
        self.do_scan = True
        self.password = None
        self._done = False
        self.server_run = False
        self.flask = None
        self.flag = False
        self.con = False
        super().__init__(slots=["#+#Back#+#\x00"],
                         value_callback=self.__connection_list_callback, do_setup_callback=True,
                         after_reset_callback=False, custom_cursor=False)

# WLAN-Selection---------
    @staticmethod
    def __suffix_map(bars, security):
        temp = ""
        match security:
            case "WPA2":
                temp += "\x07"
            case _:
                temp += ""
        match bars:
            case 1:
                temp += "\x03"
            case 2:
                temp += "\x04"
            case 3:
                temp += "\x05"
            case 4:
                temp += "\x06"
            case _:
                temp += ""
        return temp

    @staticmethod
    def __bars_to_level(bars):
        match bars:
            case "\u2582\u2584\u2586\u2588":  # corresponds to "▂▄▆█"
                return 4
            case "\u2582\u2584\u2586_":  # corresponds to "▂▄▆_"
                return 3
            case "\u2582\u2584__":  # corresponds to "▂▄__"
                return 2
            case "\u2582___":  # corresponds to "▂___"
                return 1
            case "****":
                return 4
            case "***":
                return 3
            case "**":
                return 2
            case "*":
                return 1
            case _:
                return 0

    # noinspection PyTypeChecker
    def __wifi_scan(self, rescan: bool = False, /):

        self.current_wifis = list()
        self.saved_wifis = list()
        self.found_wifis = list()

        if rescan:
            subprocess.run("sudo nmcli d wifi rescan", shell=True)

        scan = subprocess.run(f"sudo nmcli d wifi list", shell=True,
                              capture_output=True).stdout.decode().splitlines()

        columns = ["IN-USE", "BSSID", "SSID", "MODE", "CHAN", "RATE", "SIGNAL", "BARS", "SECURITY"]
        last = 0
        temp = list()

        for i in range(len(columns)):
            if i != len(columns) - 1:
                start = re.compile(columns[i]).search(scan[0], last)
                end = re.compile(columns[i + 1]).search(scan[0], start.end())
                temp.append((start.start(), end.start() - 2))
            else:
                start = re.compile(columns[i]).search(scan[0], last)
                temp.append((start.start(), None))
            last = temp[i][1]

        columns = {c: t for c, t in zip(columns, temp)}

        ls = subprocess.run(f"sudo ls -1 {self.path}", shell=True,
                            capture_output=True).stdout.decode().splitlines()

        for file in ls:
            if file.split(".")[-1] == "nmconnection":
                ac = ConfigParser()
                ac.read_string(subprocess.run(f"sudo cat '{self.path}/{file}'", shell=True,
                                              capture_output=True).stdout.decode())
                if ac["connection"]["type"] == "wifi":
                    self.saved_wifis.append({"SSID": ac["connection"]["id"], "PASSWORD": ac["wifi-security"]["psk"],
                                             "BARS": None, "SECURITY": None, "INDEX": None})

        col_filter = ["CHAN", "MODE"]
        for i, ac in enumerate(scan[1:]):
            self.found_wifis.append({key: ac[s:e].strip() for key, (s, e), in columns.items()
                                     if key not in col_filter})
            n = self.found_wifis[i]["SSID"]
            self.found_wifis[i]["BARS"] = self.__bars_to_level(self.found_wifis[i]["BARS"])
            for ac2 in self.saved_wifis:
                if n == ac2["SSID"]:
                    self.found_wifis[i]["PASSWORD"] = ac2["PASSWORD"]
                    break
                else:
                    self.found_wifis[i]["PASSWORD"] = None
            if self.found_wifis[i]["IN-USE"]:
                self.found_wifis[i]["IN-USE"] = True
                self.current_wifis.append(self.found_wifis[i])
            else:
                self.found_wifis[i]["IN-USE"] = False

        for ac in self.found_wifis:
            for i, ac2 in enumerate(self.current_wifis):
                if ac2["SSID"] == ac["SSID"] and not ac2["IN-USE"]:
                    if int(ac2["RATE"][:-7]) < int(ac["RATE"][:-7]) and int(ac2["SIGNAL"]) < int(ac["SIGNAL"]):
                        self.current_wifis[i] = ac
                    break
            else:

                self.current_wifis.append(ac)

    def __wifis_to_slots(self):

        self.slots = ["#+#Back#+#\x00"]

        try:
            self.__wifi_scan(self.do_scan)
        except Exception:
            traceback.print_exc()
        temp_f = list()
        temp_s = list()
        temp_c = list()

        for i, ac in enumerate(self.current_wifis):
            ac: dict
            exists = False
            for ac2 in [temp_f, temp_c, temp_s]:
                for ac3 in ac2:
                    if ac["SSID"] == ac3["SSID"]:
                        exists = True
                        break
                if exists:
                    break

            ac["INDEX"] = i

            if ac["IN-USE"] and not exists:
                temp_c.append(ac)
            elif ac.get("PASSWORD", None) is not None and not exists:
                temp_s.append(ac)
            elif not exists:
                temp_f.append(ac)

        self.slots.append(f"#+#--connected{'-' * 8}#+#")
        self.slots.extend([f"#+#{ac['SSID']}#+#{self.__suffix_map(ac['BARS'], ac['SECURITY'])}#+#{ac['INDEX']}"
                           for ac in temp_c])
        self.slots.append(f"#+#--saved{'-' * 12}#+#")
        self.slots.extend([f"#+#{ac['SSID']}#+#{self.__suffix_map(ac['BARS'], ac['SECURITY'])}#+#{ac['INDEX']}"
                           for ac in temp_s])
        self.slots.append(f"#+#--found{'-' * 12}#+#")
        self.slots.extend([f"#+#{ac['SSID']}#+#{self.__suffix_map(ac['BARS'], ac['SECURITY'])}#+#{ac['INDEX']}"
                           for ac in temp_f])
        self.slots.extend([f"#+#{'-' * 19}#+#", "\x01#+#Refresh#+#"])

    async def __update_signal(self):

        self.__wifi_scan()
        slot: str
        for i, slot in enumerate(self.slots):
            temp = slot.split("#+#")
            for a in self.found_wifis:
                if temp[1] == a["SSID"]:
                    self.slots[i] = f"{temp[0]}#+#{temp[1]}#+#{self.__suffix_map(a['BARS'], a['SECURITY'])}#+#{temp[3]}"

    def __connection_list_callback(self, callback_type, value, menu: RotaryMenu):
        if callback_type == "setup":
            menu.lcd.clear()
            if self.do_scan:
                menu.lcd.cursor_pos = (1, 0)
                menu.lcd.write_string("Searching Networks!")
            menu.lcd.create_char(0, self.back_symbol)
            menu.lcd.create_char(1, self.refresh)
            menu.lcd.create_char(3, self.connection_low)
            menu.lcd.create_char(4, self.connection_medium)
            menu.lcd.create_char(5, self.connection_high)
            menu.lcd.create_char(6, self.connection_full)
            menu.lcd.create_char(7, self.lock)

            try:

                self.__wifis_to_slots()
            except Exception:
                print(traceback.print_exc())

            async def connection_updater():
                while self.value_callback == self.__connection_list_callback and menu.current_menu == self:
                    await asyncio.sleep(20)
                    if self.value_callback == self.__connection_list_callback and menu.current_menu == self:
                        await self.__update_signal()
                        while menu.wait:
                            await asyncio.sleep(0.01)
                        if self.value_callback == self.__connection_list_callback and menu.current_menu == self:
                            menu.wait = True
                            menu.menu(True)
                            menu.wait = False
                        else:
                            break
                    else:
                        break

            asyncio.run_coroutine_threadsafe(connection_updater(), menu.loop)

        if callback_type == "press":
            if self.slots[value].split("#+#")[1] == "Back":
                menu.set(self.pr_menu if not None else menu.main)
            elif self.slots[value].split("#+#")[1] == "Refresh":
                menu.lcd.clear()
                menu.lcd.cursor_pos = (1, 0)
                menu.lcd.write_string("Searching Networks!")
                self.do_scan = True
                self.__wifis_to_slots()
                menu.reset_menu()
            elif self.slots[value] in [f"#+#--connected{'-' * 8}#+#", f"#+#--saved{'-' * 12}#+#", f"#+#{'-' * 19}#+#",
                                       f"#+#--found{'-' * 12}#+#"]:
                pass
            else:
                self.current_index = int(self.slots[value].split("#+#")[3])
                self.value_callback = self.__ac_callback
                self.flag = True
                menu.set(self)

    # AC-Settings
    def __connection_slots(self):
        self.slots = ["#+#Back#+#\x00"]
        temp = self.current_wifis[self.current_index]["IN-USE"]
        self.slots.append("#+#Disconnect#+#\x01" if temp else "#+#Connect#+#\x01")

    def __disconnect(self, menu, display=True):
        if display:
            menu.lcd.clear()
            menu.lcd.cursor_pos = (1, 0)
            menu.lcd.write_string("Disconnecting...")
        subprocess.run("sudo nmcli d disconnect wlan0", shell=True, capture_output=True)
        menu.reset_menu()

    def __connection_attempt(self, menu, ssid, password=None):
        try:
            if password is None:
                command = ["sudo", "nmcli", "d", "wifi", "connect", ssid]
            else:
                command = ["sudo", "nmcli", "d", "wifi", "connect", ssid, "password", password]
            subprocess.run(command, capture_output=True, timeout=120, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error: {e.returncode}\n{e.stdout}\n{e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            print("Connection attempt timed out.")
            return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

        success = False
        try:
            for i in range(120):
                if ssid in subprocess.run("nmcli c show --active | grep wlan0", shell=True, capture_output=True,
                                          text=True).stdout:
                    success = True
                    break
                else:
                    time.sleep(1)
        except:
            print(traceback.print_exc())

        if not success:
            subprocess.run(f"sudo nmcli c delete '{ssid}'",
                           shell=True, capture_output=True, ).stdout.decode()

        return success

    def __contin(self, menu):
        menu.wait = False
        self.flag = True
        self.con = False
        async def countdown():
            c = 10
            while c > 0 and self.flag:
                await asyncio.sleep(1)
                c -= 1
                menu.lcd.cursor_pos = (1, 0)
                menu.lcd.write_string(f"wait 0{c}s to continue")
            if self.flag:
                self.flag = False
        menu.lcd.clear()
        menu.lcd.write_string("Press to Retry, or\r\n")
        menu.lcd.write_string("wait 10s to continue")
        asyncio.run_coroutine_threadsafe(countdown(), menu.loop)
        while self.flag:
            time.sleep(0.1)
        menu.wait = True
        self.flag = False
        return not self.con




    def __password_promt(self, menu):
        def get_local_ip():
            output = subprocess.run("ip addr show wlan0 | grep inet", shell=True,
                                    capture_output=True).stdout.decode()
            pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            local_ip = re.search(pattern, output)[0]
            print(local_ip)
            return local_ip
        self._done = False
        subprocess.run(f"sudo nmcli d wifi hotspot con-name 'GH-HS' ssid 'GH-HS' password 'gravihub'", shell=True)
        try:
            path = Path(shutil.which("flask"))
            command = [path, "--app", "app", "run", "--host", "0.0.0.0", "--port", "5000"]
            self.flask = subprocess.Popen(command,
                                          cwd=Path(os.getcwd()) / "MenuTypes/NetworkSettings", stdout=subprocess.PIPE)
        except:
            print(traceback.print_exc())
        self.server_run = True
        menu.lcd.clear()
        ip = get_local_ip()

        menu.lcd.write_string("Connect to GH-HS\n\r")
        menu.lcd.write_string("pw: gravihub, open\n\r")
        menu.lcd.write_string("http://[ip]:5000\r\n")
        menu.lcd.write_string(f"ip: {ip}\n\r")

        timeout = 240
        flask_stdout_fd = self.flask.stdout.fileno()
        os.set_blocking(flask_stdout_fd, False)
        while timeout > 0:
            pw = self.flask.stdout.readline().rstrip().decode('utf-8')
            if pw.startswith("Pw:"):
                self.password = pw[3:].strip()
                print(self.password)
                break
            time.sleep(1)
            timeout -= 1
        self.flask.terminate()
        self.server_run = False
        menu.lcd.clear()
        menu.lcd.cursor_pos = (1, 0)

        if self.password and not timeout == 0:
            menu.lcd.write_string("Got Password!")
            time.sleep(1)
            menu.lcd.clear()
            menu.lcd.cursor_pos = (1, 0)
            menu.lcd.write_string("Connecting...")
            temp = self.current_wifis[self.current_index]["SSID"]
            success = self.__connection_attempt(menu, temp, password=self.password)
            print(success)
            if not success:
                menu.lcd.clear()
                menu.lcd.cursor_pos = (1, 0)
                menu.lcd.write_string("An Error occurred!")
                time.sleep(1)
                if self.__contin(menu):
                    self.do_scan = True
                    menu.reset_menu()
                else:
                    self.__password_promt(menu)
            else:
                menu.lcd.clear()
                menu.lcd.cursor_pos = (1, 0)
                menu.lcd.write_string("Successful!")
                time.sleep(1)
                self.do_scan = True
                menu.reset_menu()
        elif timeout == 0:
            menu.lcd.write_string("Timeout!")
            time.sleep(1)
            if self.__contin(menu):
                self.do_scan = True
                menu.reset_menu()
            else:
                self.__password_promt(menu)
        else:
            menu.lcd.write_string("An Error occurred!")
            time.sleep(1)
            if self.__contin(menu):
                self.do_scan = True
                menu.reset_menu()
            else:
                self.__password_promt(menu)

    def __connect(self, menu, display=True):
        self.password = ""
        if display:
            menu.lcd.clear()
            menu.lcd.cursor_pos = (1, 0)
            menu.lcd.write_string("Connecting...")

        temp = self.current_wifis[self.current_index]["PASSWORD"]
        temp2 = self.current_wifis[self.current_index]["SECURITY"]
        if temp is None and temp2 is not None:
            print("New")
            self.__password_promt(menu)
        else:
            print("Old")
            temp = self.current_wifis[self.current_index]["SSID"]
            success = self.__connection_attempt(menu, temp)
            print(success)
            if not success:
                menu.lcd.clear()
                menu.lcd.cursor_pos = (1, 0)
                menu.lcd.write_string("An Error occurred!")
                time.sleep(1)
                if self.__contin(menu):
                    self.do_scan = True
                    menu.reset_menu()
                else:
                    self.__password_promt(menu)
            else:
                menu.lcd.clear()
                menu.lcd.cursor_pos = (1, 0)
                menu.lcd.write_string("Successful!")
                time.sleep(1)
                self.do_scan = True
                menu.reset_menu()

    def __ac_callback(self, callback_type, value, menu: RotaryMenu):
        if callback_type == "setup":

            if not self.flag:
                self.value_callback = self.__connection_list_callback
                self.do_scan = True
                self.__connection_list_callback(callback_type, value, menu)
                return
            else:
                self.flag = False

            menu.lcd.create_char(0, self.back_symbol)
            menu.lcd.create_char(1, self.forward_symbol)

            self.__connection_slots()

        if callback_type == "press":
            if self.flag:
                self.flag = False
                self.con = True
            elif self.slots[value].split("#+#")[1] == "Back":
                self.value_callback = self.__connection_list_callback
                self.do_scan = False
                menu.set(self)
            elif self.slots[value].split("#+#")[1] == "Disconnect":
                self.__disconnect(menu)
            elif self.slots[value].split("#+#")[1] == "Connect":
                self.__connect(menu)

    def stop_server(self):
        if self.server_run:
            self.flask.terminate()
