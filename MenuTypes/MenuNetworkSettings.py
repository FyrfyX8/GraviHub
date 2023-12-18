from RotaryMenu import MenuType, RotaryMenu
from RPLCD.i2c import CharLCD

import subprocess
import yaml
import asyncio

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
        super().__init__(slots=["#+#Back#+#\x00"] + self.saved_connections, value_callback=self.value_callback,
                         do_setup_callback=True,
                         after_reset_callback=False, custom_cursor=False)

    def value_callback(self, callback_type, value, menu: RotaryMenu):
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

            saved = subprocess.run(f"sudo cat {self.config_file}", shell=True, capture_output=True)
            temp = yaml.safe_load(saved.stdout)
            self.saved_connections = [ap for ap in temp["network"]["wifis"]["wlan0"]["access-points"]]
            self.slots = ["#+#Back#+#\x00"] + [f"\x07#+#{ap}#+#" for ap in self.saved_connections]
            try:
                avaiablbe = Cell.all("wlan0")
                for cell in avaiablbe:
                    print(cell.ssid)
            except Exception as e:
                print(f"ex: {e}")

            async def connection_updater():
                pass


        if callback_type == "press":
            if value == 1:
                menu.set(self.pr_menu if not None else menu.main)
