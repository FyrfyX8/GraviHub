



import time
from abc import ABC
from RotaryMenu.encoder import Encoder
from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
import asyncio
from pathlib import Path

defaultLCD = CharLCD(i2c_expander="PCF8574", address=0x27, port=1, cols=20, rows=4, dotsize=8)


class MenuType(ABC):
    def __init__(self, slots: list = None, value_callback=None, do_setup_callback=False, after_reset_callback=False,
                 custom_cursor=False):
        self.slots = slots
        self.value_callback = value_callback
        self.do_setup_callback = do_setup_callback
        self.after_reset_callback = after_reset_callback
        self.custom_cursor = custom_cursor

    def change_slot(self, index: int, slot: str):
        self.slots[index] = slot



class Main(MenuType):
    def __init__(self, slots: list, value_callback, do_setup_callback=False, after_reset_callback=False, custom_cursor=False):
        super().__init__(slots=slots, value_callback=value_callback, do_setup_callback=do_setup_callback,
                         after_reset_callback=after_reset_callback, custom_cursor=custom_cursor)


class Sub(MenuType):
    def __init__(self, slots: list, value_callback,  do_setup_callback=False, after_reset_callback=False, custom_cursor=False):
        super().__init__(slots=slots, value_callback=value_callback, do_setup_callback=do_setup_callback,
                         after_reset_callback=after_reset_callback, custom_cursor=custom_cursor)


class File(MenuType):
    def __init__(self, path: Path, value_callback, *, extension_filter: list = [".py"], show_folders=True,
                 pr_slots: list = [], dir_affix: str = "#+#", custom_folder_behaviour=False,
                 do_setup_callback=False,
                 after_reset_callback=False, custom_cursor=False, **kwargs):
        self.path = path
        self.current_path = path
        self.extension_filter = extension_filter
        self.file_menu_depth = 0
        self.show_folders = show_folders
        self.dir_affix = dir_affix.split("#+#", 1)
        self.file_affix = kwargs
        self.pr_slots = pr_slots
        self.fmd0_slots = []
        self.pr_slots_last_index = len(pr_slots) - 1
        self.custom_folder_behaviour = custom_folder_behaviour

        super().__init__(self.pr_slots + self.fmd0_slots + self.files_to_slots(), value_callback=value_callback, do_setup_callback=do_setup_callback,
                         after_reset_callback=after_reset_callback, custom_cursor=custom_cursor)

    def files_to_slots(self):
        file_slots = []
        if self.file_menu_depth > 0:
            file_slots.append(f"{self.dir_affix[0]}#+#..#+#{self.dir_affix[1]}")
        for folder in self.current_path.iterdir():
            if folder.is_dir() and not folder.name.startswith("__"):
                file_slots.append(f"{self.dir_affix[0]}#+#{folder.name}#+#{self.dir_affix[1]}")
        for file in self.current_path.iterdir():
            if file.is_file() and file.suffix in self.extension_filter:
                affix_filter = ""
                for extension in file.suffixes:
                    affix_filter = f"{affix_filter}{extension[1:]}_"
                affix_filter = f"{affix_filter}affix"
                if self.file_affix.get(affix_filter) is not None:
                    backed_file_affix = str(self.file_affix.get(affix_filter)).split("#+#", 1)
                    file_slots.append(f"{backed_file_affix[0]}#+#{file.name}#+#{backed_file_affix[1]}")
                else:
                    file_slots.append(f"#+#{file.name}#+#")
        return file_slots

    def return_to_parent(self):
        self.file_menu_depth -= 1
        self.set_path(self.current_path.parent)

    def set_path(self, path: Path, file_menu_depth: int = None):
        if file_menu_depth is not None:
            if file_menu_depth < 0:
                raise ValueError
            else:
                self.file_menu_depth = file_menu_depth
        self.current_path = path
        self.slots = self.pr_slots + self.files_to_slots()

    def move_to_dir(self, dir_name: str):
        if (self.current_path / dir_name).is_dir():
            self.file_menu_depth += 1
            self.set_path(self.current_path / dir_name)

    def return_to_default(self):
        self.set_path(self.path, 0)

    def update_pr_slots(self):
        if self.file_menu_depth == 0:
            self.slots = self.pr_slots + self.fmd0_slots + self.files_to_slots()
            self.pr_slots_last_index = len(self.pr_slots + self.fmd0_slots) - 1
        else:
            self.slots = self.pr_slots + self.files_to_slots()
            self.pr_slots_last_index = len(self.pr_slots) - 1


class RotaryMenu:
    def __init__(self, lcd: CharLCD = defaultLCD, *, left_pin: int, right_pin: int, button_pin: int, main: Main,
                 menu_timeout: int = 0):

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(button_pin, GPIO.RISING, callback=self.button_press, bouncetime=300)
        encoder = Encoder(left_pin, right_pin, self.value_changed)

        self.lcd = lcd
        self.loop = asyncio.get_event_loop()
        self.main = main
        self.menu_timeout = menu_timeout
        self.timeout_reset = False
        self.current_menu = self.main
        self.wait = False
        self.index = 0
        self.max_index = self.get_max_index()
        self.shift = 0
        self.max_shift = self.get_max_shift()
        self.cursor_pos = 0
        self.max_cursor_pos = self.get_max_cursor_pos()
        self.scrolling_start = True
        self.scrolling = False
        self.end_scrolling = False
        self.scrolling_end = False
        self.backed_slots = []
        self.get_backed_slots()
        asyncio.run_coroutine_threadsafe(self.timeout_timer(), self.loop)

    def get_max_index(self):
        print("max index:", len(self.current_menu.slots) - 1)
        return len(self.current_menu.slots) - 1

    def get_max_shift(self):
        max_shift = len(self.current_menu.slots) - self.lcd.lcd.rows

        if max_shift >= 0:
            print("max shift", max_shift)
            return max_shift
        else:
            print("max shift", 0)
            return 0

    def get_max_cursor_pos(self):
        return self.lcd.lcd.rows

    def get_backed_slots(self):
        backed_slots = []
        index = 0
        for i in self.current_menu.slots:
            slot = self.current_menu.slots[index].split("#+#", 2)
            space = self.lcd.lcd.cols - len(slot[0]) - len(slot[2]) - 1
            if self.get_overflow(index):
                backed_name = slot[1][0:space]
            else:
                backed_name = slot[1] + " " * (space - len(slot[1]))
            backed_slots.append(f"{slot[0]}{backed_name}{slot[2]}")
            index += 1
        self.backed_slots = backed_slots

    async def timeout_timer(self):
        clock = 0
        while self.menu_timeout > 0:
            if clock == self.menu_timeout and self.current_menu != self.main:
                print("back-to-main")
                self.set_wait()
                self.set(self.main)
                self.reset_wait()
                clock = 0
            if self.timeout_reset:
                self.timeout_reset = False
                clock = 0
            else:
                await asyncio.sleep(1)
                if self.current_menu != self.main and not self.wait:
                    clock += 1
                    print(clock)

    def get_overflow(self, index):
        slot = self.current_menu.slots[index].split("#+#", 2)
        len_prefix = len(slot[0])
        len_name = len(slot[1])
        len_suffix = len(slot[2])
        return (len_name + len_suffix + len_prefix + 1) >= self.lcd.lcd.cols

    def reset_wait(self):
        print("wait reset")
        self.wait = False

    def set_wait(self):
        self.wait = True

    def set(self, menu: MenuType):
        self.current_menu = menu
        if self.current_menu.do_setup_callback:
            self.callback("setup", value="none")
        self.reset_menu(reset_wait=False)
        if self.current_menu.after_reset_callback:
            self.callback("after_setup", value="none")

    def callback(self, callback_type: str, value=None):
        self.current_menu.value_callback(callback_type, value)

    async def start_scrolling(self):

        if self.get_overflow(self.index) and not self.current_menu.custom_cursor:
            self.scrolling_start = True
            shift = 0
            for t in range(1000):
                if not self.end_scrolling:
                    await asyncio.sleep(0.001)
                else:
                    return
            self.scrolling_start = False
            self.scrolling = True
            slot = self.current_menu.slots[self.index].split("#+#", 2)
            space = self.lcd.lcd.cols - len(slot[0]) - len(slot[2]) - 1
            for i in range(len(slot[1]) - space + 1):
                if self.end_scrolling:
                    self.scrolling = False
                    return
                self.lcd.cursor_pos = (self.cursor_pos, 1)
                shift_name = slot[1][shift:shift + space]
                print(shift_name)
                self.lcd.write_string(f"{slot[0]}{shift_name}{slot[2]}")
                shift += 1
                for t in range(25):
                    if not self.end_scrolling:
                        await asyncio.sleep(0.01)
                    else:
                        self.scrolling = False
                        return
            self.scrolling_end = True
            return

    def stop_scrolling(self, row, index):
        self.end_scrolling = True
        while self.scrolling or self.scrolling_start:
            if self.scrolling_start:
                self.scrolling_start = False
            elif self.scrolling_end:
                self.scrolling_end = False
                self.scrolling = False
            time.sleep(0.01)
        self.end_scrolling = False
        self.reset_wait()
        if not self.scrolling_start:
            self.lcd.cursor_pos = (row, 1)
            self.lcd.write_string(self.backed_slots[index])

    def cursor(self, pr_cursor_pos):
        if not self.current_menu.custom_cursor:
            self.lcd.cursor_pos = (pr_cursor_pos, 0)
            self.lcd.write_string(" ")
            self.lcd.cursor_pos = (self.cursor_pos, 0)
            self.lcd.write_string(">")

    def reset_cursor(self):
        pr_cursor_pos = self.cursor_pos
        self.cursor_pos = 0
        self.cursor(pr_cursor_pos)

    def update_current_slot(self):
        update_index = self.shift + self.cursor_pos
        self.get_backed_slots()
        self.lcd.cursor_pos = (self.cursor_pos, 1)
        self.lcd.write_string(self.backed_slots[update_index])

    def menu(self):
        current_index = self.shift
        current_row = 0
        for t in range(self.lcd.lcd.rows):
            try:
                self.lcd.cursor_pos = (current_row, 1)
                self.lcd.write_string(self.backed_slots[current_index])
                current_row += 1
                current_index += 1
            except IndexError:
                pass

    def reset_menu(self, reset_wait=True):
        self.lcd.clear()
        time.sleep(0.01)
        if isinstance(self.current_menu, File):
            self.current_menu.update_pr_slots()
        self.index = 0
        self.shift = 0
        self.max_cursor_pos = self.get_max_cursor_pos()
        self.max_index = self.get_max_index()
        self.max_shift = self.get_max_shift()
        if self.scrolling:
            self.end_scrolling = True
            while self.scrolling:
                if self.scrolling_end:
                    self.scrolling_end = False
                    self.scrolling = False
                time.sleep(0.01)
            self.end_scrolling = False
        self.get_backed_slots()
        self.reset_cursor()
        self.menu()
        time.sleep(0.01)
        if reset_wait:
            self.reset_wait()

    def value_changed(self, value, direction):
        if not self.wait:
            print("value")
            self.set_wait()
            self.timeout_reset = True
            if self.current_menu.custom_cursor:
                self.callback("direction", value=direction)
                self.reset_wait()
            else:
                pr_index = self.index
                pr_shift = self.shift
                pr_cursor_pos = self.cursor_pos
                if direction == "R":
                    if self.index != 0:
                        self.cursor_pos -= 1
                        self.index -= 1
                        if self.cursor_pos == -1:
                            self.cursor_pos = 0
                            if self.shift != 0:
                                self.shift -= 1
                else:
                    if self.index != self.max_index:
                        self.cursor_pos += 1
                        self.index += 1
                        if self.cursor_pos == self.max_cursor_pos:
                            self.cursor_pos = self.max_cursor_pos - 1
                            if self.shift != self.max_shift:
                                self.shift += 1
                if self.scrolling or self.scrolling_start:
                    self.stop_scrolling(pr_cursor_pos, pr_index)
                if self.cursor_pos != pr_cursor_pos:
                    self.cursor(pr_cursor_pos)
                if self.shift != pr_shift:
                    self.menu()
                if self.get_overflow(self.index):
                    asyncio.run_coroutine_threadsafe(self.start_scrolling(), self.loop)
                self.reset_wait()


    def button_press(self, arg):
        def pressed():
            print("pressed")
            if isinstance(self.current_menu, File):
                if self.index <= self.current_menu.pr_slots_last_index:
                    self.callback("press", value=self.index)
                elif self.current_menu.file_menu_depth >= 1 and self.index == self.current_menu.pr_slots_last_index + 1:
                    self.current_menu.return_to_parent()
                    self.reset_menu()
                else:
                    slot: str = self.current_menu.slots[self.index]
                    check_path = self.current_menu.current_path / slot.split("#+#", 2)[1]
                    if check_path.is_dir():
                        if not self.current_menu.custom_folder_behaviour:
                            self.current_menu.move_to_dir(slot.split("#+#", 2)[1])
                            self.reset_menu()
                        else:
                            self.callback("dirpress", value=check_path)
                    elif check_path is not None:
                        if check_path.is_file():
                            self.callback("filepress", value=check_path)
                    else:
                        self.callback("press", value=self.index)
            else:
                self.callback("press", value=self.index)
            print("reset")
            self.reset_wait()

        async def button_check():
            if not self.wait:
                self.set_wait()
                self.timeout_reset = True
                await self.loop.run_in_executor(None, pressed)

        asyncio.run_coroutine_threadsafe(button_check(), self.loop)
