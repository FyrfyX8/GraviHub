from RotaryMenu import MenuType, RotaryMenu
from RPLCD.i2c import CharLCD

import subprocess
import yaml
import asyncio
import re


class MenuNetworkSettings(MenuType):

    connection_none = (
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b10000
    )

    connection_low = (
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b01000,
        0b11000
    )

    connection_medium = (
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00100,
        0b01100,
        0b11100
    )

    connection_high = (
        0b00000,
        0b00000,
        0b00000,
        0b00000,
        0b00010,
        0b00110,
        0b01110,
        0b11110
    )

    connection_full = (
        0b00000,
        0b00000,
        0b00000,
        0b00001,
        0b00011,
        0b00111,
        0b01111,
        0b11111
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

    def __init__(self, config_file, back_symbol, forward_symbol):
        self.config_file = config_file
        self.back_symbol = back_symbol
        self.forward_symbol = forward_symbol
        self.pr_menu = None
        self.saved_connections = []
        self.found_wifis = {}
        super().__init__(slots=["#+#Back#+#\x00"] + self.saved_connections, value_callback=self.__value_callback,
                         do_setup_callback=True,
                         after_reset_callback=False, custom_cursor=False)

    def __wifi_scan(self):
        scan = subprocess.run("sudo iw wlan0 scan", shell=True, capture_output=True).stdout.decode()


        def dbm_to_level(dbm):
            match dbm:
                case _ if signal >= -50:
                    return 4
                case _ if -60 <= signal < -50:
                    return 3
                case _ if -70 <= signal < -60:
                    return 2
                case _ if -80 <= signal < -70:
                    return 1
                case _:
                    return 0

        temp = []

        for m in re.finditer("signal:", scan):
            ssid = scan[scan.find("SSID:", m.end()) + 6: scan.find("\n", scan.find("SSID:", m.end()))]
            signal = float(scan[m.end() + 1:scan.find("dBm", m.end())])
            temp.append((ssid, dbm_to_level(signal)))
        self.found_wifis = {n: {"signal": s, "password": None} for n, s in sorted(temp, key=lambda k: k[1]) if n}
        print(self.found_wifis)
    def __wifis_to_slots(self):
        def signal_map(signal):
            match signal:
                case 0:
                    return "\x02"
                case 1:
                    return "\x03"
                case 2:
                    return "\x04"
                case 3:
                    return "\x05"
                case 4:
                    return "\x06"
                case _:
                    return ""

        self.slots = ["#+#Back#+#\x00"]
        
        self.__wifi_scan()
        saved = subprocess.run(f"sudo cat {self.config_file}", shell=True, capture_output=True)
        temp = yaml.safe_load(saved.stdout)

        self.saved_connections = {n: {"signal": self.found_wifis.get(n, {"signal": None})["signal"], "password":
                                  temp["network"]["wifis"]["wlan0"]["access-points"][n]["password"]}
                                  for n in temp["network"]["wifis"]["wlan0"]["access-points"]}

        self.slots.extend([f"\x07#+#{n}#+#{signal_map(self.saved_connections[n]['signal'])}"
                           for n in self.saved_connections])
        self.slots.extend([f"#+#{n}#+#{signal_map(self.found_wifis[n]['signal'])}" for n in self.found_wifis])
        self.slots.append("#+#Reload#+#")


    def __value_callback(self, callback_type, value, menu: RotaryMenu):
        print("test")
        if callback_type == "setup":
            menu.lcd.create_char(0, self.back_symbol)
            menu.lcd.create_char(1, self.forward_symbol)
            menu.lcd.create_char(2, self.connection_none)
            menu.lcd.create_char(3, self.connection_low)
            menu.lcd.create_char(4, self.connection_medium)
            menu.lcd.create_char(5, self.connection_high)
            menu.lcd.create_char(6, self.connection_full)
            menu.lcd.create_char(7, self.lock)
            try:
                self.__wifis_to_slots()
            except Exception as e:
                print(f"error: {e}")

            async def connection_updater():
                pass
        if callback_type == "press":
            if value == 1:
                menu.set(self.pr_menu if not None else menu.main)

