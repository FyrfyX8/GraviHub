import time
from abc import ABC
from RotaryMenu.encoder import Encoder
from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
import asyncio
from pathlib import Path

defaultLCD = CharLCD(i2c_expander="PCF8574", address=0x27, port=1, cols=20, rows=4, dotsize=8)


class MenuType(ABC):
    def __init__(self, slots: list = None, value_callback=None,):
        self.slots = slots
        self.value_callback = value_callback

    def change_slot(self, index: int, slot: str):
        del self.slots[index]
        self.slots.insert(index, slot)



class Main(MenuType):
    def __init__(self, slots: list, value_callback):
        super().__init__(slots=slots, value_callback=value_callback)


class Sub(MenuType):
    def __init__(self, slots: list, value_callback):
        super().__init__(slots=slots, value_callback=value_callback)


class File(MenuType):
    def __init__(self, path: Path, value_callback, extension_filter: str = None, show_folders: bool = True):
        self.path = path
        self.extension_filter = extension_filter
        self.file_menu_depth = 0
        self.show_folders = show_folders
        super().__init__(slots=self.files_to_slots(), value_callback=value_callback)

    def files_to_slots(self):
        pass



class RotaryMenu:

    def __init__(self, lcd: CharLCD = defaultLCD, *, left_pin: int,
                 right_pin: int, button_pin: int, main: Main,
                 menu_timeout: int = 0, separator: str= "#/#"):

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(button_pin, GPIO.RISING, callback=self.button_press, bouncetime=300)
        encoder = Encoder(left_pin, right_pin, self.value_changed)

        self.lcd = lcd
        self.loop = asyncio.get_event_loop()
        self.main = main
        self.menu_timeout = menu_timeout
        self.current_menu = self.main
        self.wait = False
        self.custom_cursor = False
        self.index = 0
        self.max_index = self.get_max_index()
        self.shift = 0
        self.max_shift = self.get_max_shift()
        self.cursor_pos = 0
        self.max_cursor_pos = self.get_max_cursor_pos()
        self.separator = separator
        self.scrolling = False
        self.end_scrolling = False


    def get_max_index(self):
        print(len(self.current_menu.slots) - 1)
        return len(self.current_menu.slots) - 1

    def get_max_shift(self):
        print(len(self.current_menu.slots) - self.lcd.lcd.rows)
        return len(self.current_menu.slots) - self.lcd.lcd.rows

    def get_max_cursor_pos(self):
        return self.lcd.lcd.rows - 1

    def return_to_main(self, do_setup_callback: bool):
        self.set(self.main, do_setup_callback)

    def get_overflow(self, index):
        slot = self.current_menu.slots[index].split(self.separator)
        len_prefix = len(slot[0])
        len_name = len(slot[1])
        len_suffix = len(slot[2])
        return (len_name + len_suffix + len_prefix + 1) > self.lcd.lcd.cols

    def toggle_wait(self):
        self.wait = not self.wait

    def toggle_custom_cursor(self):
        self.custom_cursor = not self.custom_cursor

    def set(self, menu: MenuType, do_setup_callback: bool):
        self.current_menu = menu
        if do_setup_callback:
            self.callback("setup")

    def callback(self, callback_type: str, value=None):
        self.current_menu.value_callback(callback_type, value)

    def start_scrolling(self):
        def scrolling():
            shift = 0
            for t in range(100):
                if self.end_scrolling:
                    self.scrolling = False
                    return
                else:
                    time.sleep(0.01)
            slot = self.current_menu.slots[self.index].split(self.separator)
            space = self.lcd.lcd.cols - len(slot[0]) - len(slot[2]) - 1
            for i in range(len(slot[1])):
                if self.end_scrolling:
                    self.scrolling = False
                    return
                self.lcd.cursor_pos = (self.cursor_pos, 1)
                shift_name = slot[1][shift:shift + space]
                self.lcd.write_string(f"{slot[0]}{shift_name}{slot[2]}")
                for t in range(20):
                    if self.end_scrolling:
                        self.scrolling = False
                        return
                    else:
                        time.sleep(0.01)
            while True:
                if self.end_scrolling:
                    self.scrolling = False
                    return
                else:
                    time.sleep(0.01)

        if self.get_overflow(self.index) and not self.custom_cursor:
            self.scrolling = True
            #asyncio.run_coroutine_threadsafe(scrolling(), self.loop)
            scrolling()

    def stop_scrolling(self, index, row):
        self.toggle_wait()
        self.end_scrolling = True
        while self.scrolling:
            time.sleep(0.01)
        self.end_scrolling = False

    def cursor(self,pr_cursor_pos):
        self.lcd.cursor_pos = (pr_cursor_pos, 0)
        self.lcd.write_string(" ")
        self.lcd.cursor_pos = (self.cursor_pos, 0)
        self.lcd.write_string(">")

    def reset_cursor(self):
        pr_cursor_pos = self.cursor_pos
        self.cursor_pos = 0
        self.cursor(pr_cursor_pos)
    def menu(self):
        def get_backed_slots():
            backed_slots = []
            index = 0
            backed_name = ""
            for i in self.current_menu.slots:
                slot = self.current_menu.slots[index].split(self.separator, 2)
                space = self.lcd.lcd.cols - len(slot[0]) - len(slot[2]) - 1
                if self.get_overflow(index):
                    backed_name = slot[1][0:space]
                else:
                    backed_name = slot[1] + " " * (space - len(slot[1]))
                backed_slots.append(f"{slot[0]}{backed_name}{slot[2]}")
                index += 1
            return backed_slots

        slots = get_backed_slots()
        current_index = self.shift
        current_row = 0
        for t in range(4):
            self.lcd.cursor_pos = (current_row, 1)
            self.lcd.write_string(slots[current_index])
            current_row += 1
            current_index += 1



    def reset_menu(self):
        self.lcd.clear()
        pr_index = self.index
        pr_cursor_pos = self.cursor_pos
        self.index = 0
        self.shift = 0
        self.stop_scrolling(pr_index, pr_cursor_pos)
        self.reset_cursor()
        self.menu()

    def value_changed(self, value, direction):
        if not self.wait:
            self.toggle_wait()
            if self.custom_cursor:
                self.callback("direction", value=direction)
            else:
                pr_index = self.index
                pr_shift = self.shift
                pr_cursor_pos = self.cursor_pos
                if direction == "R":
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
                elif self.cursor_pos == self.max_cursor_pos + 1:
                    self.cursor_pos = self.max_cursor_pos
                    if self.shift != self.max_shift:
                        self.shift += 1
                if self.scrolling:
                    self.stop_scrolling(pr_index, pr_cursor_pos)
                if self.cursor_pos != pr_cursor_pos:
                    self.cursor(pr_cursor_pos)
                if self.shift != pr_shift:
                    self.menu()
                if self.get_overflow(self.index):
                    self.start_scrolling()
                self.toggle_wait()

    def button_press(self, arg):
        def pressed():
            self.callback("press", value=self.index)
            print("tes")
            self.toggle_wait()

        async def button_check():
            if not self.wait:
                self.toggle_wait()
                await self.loop.run_in_executor(None, pressed)

        asyncio.run_coroutine_threadsafe(button_check(), self.loop)






