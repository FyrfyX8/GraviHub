from encoder import Encoder
from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
import asyncio
from pathlib import Path

defultLCD = CharLCD(i2c_expander="PCF8574", address=0x27, port=1, cols=20, rows=4, dotsize=8)

class NoMenuTypeSet(Exception):
    "Raised when object using MenuType is created"
    pass


class MenuType:
    def __init__(self, slots: list = None, callback= None,):
        self.slots = slots
        self.callback = callback

    def change_slot(self, index: int, slot: str):
        del self.slots[index]
        self.slots.insert(index, slot)


class Main(MenuType):
    def __init__(self, slots: list = None, callback= None):
        super().__init__(slots=slots, callback=callback)


class Sub(MenuType):
    def __init__(self, slots: list = None, callback= None):
        super().__init__(slots=slots, callback=callback)


class File(MenuType):
    def __init__(self, path: Path = None, callback= None, filter: str = None):
        self.path = path
        self.filter = filter
        self.file_menu_deph = 0
        super().__init__(slots=self.files_to_slots(), callback=callback)

    def files_to_slots(self):
        pass


class RotaryMenu:

    def __init__(self, lcd: CharLCD = defultLCD, left_pin: int = None,
                 right_pin: int = None, button_pin: int = None, main: Main = None,
                 menu_timeout: int = 0):

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(button_pin, GPIO.RISING, callback=self.buttonPress, bouncetime=300)

        self.encoder = Encoder(left_pin, right_pin, self.value_changed)
        self.main = main
        self.menu_timeout = menu_timeout
        self.current_menu = self.main
        self.wait = True
        self.custom_cursor = False
        self.index = 0
        self.max_index = self.get_max_index()
        self.shift = 0
        self.max_shift = self.get_max_shift()
        self.cursor_pos = 0

    def get_max_index(self):
        return len(self.current_menu.slots)

    def get_max_shift(self):
        return len(self.current_menu.slots) - 3

    def set(self, menu: MenuType, do_setup_callback: bool):
        self.current_menu = menu
        if do_setup_callback:
            self.callback("setup")


    def callback(self, callback_type: str):
        self.current_menu.callback(callback_type)

    def value_changed(self, value, direction):
        if self.custom_cursor:
            self.callback("value")
        else:
            pr_index = self.index
            pr_shift = self.shift
            pr_cursor_pos = self.cursor_pos
            if direction is "R":
                if self.index != 0:
                    self.cursor_pos -= 1
                    self.index -= 1
            else:
                if self.index != self.max_index:
                    self.cursor_pos += 1
                    self.index += 1
            if self.cursor_pos == -1:
                self.cursor_pos = 0
                if self.shift != 0:
                    self.shift -= 1
            elif self.cursor_pos == 4:
                self.cursor_pos = 3
                if self.shift != self.max_shift:
                    self.shift += 1




    def button_press(self, arg):
        def pressed():
            self.callback("press")
        async def button_check():
            if self.wait:
                await asyncio.get_event_loop().run_in_executor(None, pressed)

        asyncio.run_coroutine_threadsafe(button_check(), asyncio.get_running_loop())






