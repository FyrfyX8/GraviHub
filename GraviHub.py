from RotaryMenu import *
from gravitraxconnect import gravitrax_bridge as gb
from gravitraxconnect import gravitrax_constants as gc
from RPLCD.i2c import CharLCD
from configparser import ConfigParser
from pathlib import Path
from MenuTypes.MenuNetworkSettings import *

import fcntl
import socket
import struct
import sys
import time
import requests
import RPi.GPIO as GPIO
import asyncio
import importlib.util
import pyudev
import os
import shutil
import getpass

# GraviHub v2.0.0

# settings.ini
settings = ConfigParser()
settings.read("settings.ini")

# lcd
lcd = CharLCD(i2c_expander=settings["lcd"]["i2c_expander"], address=0x27, port=1,
              cols=int(settings["lcd"]["cols"]), rows=int(settings["lcd"]["rows"]),
              dotsize=int(settings["lcd"]["dotsize"]))

# Variables for the Bridges
bridges_MAC = ["none", "none", "none", "none", "none", "none"]
bridges = [gb.Bridge(), gb.Bridge(), gb.Bridge(), gb.Bridge(), gb.Bridge(), gb.Bridge()]
battery_levels = [0, 0, 0, 0, 0, 0]
scripts = ["none", "none", "none", "none", "none", "none"]
modules = {}
bridge_count = 0
bridge_mode = False

# Encoder settings
encoder_button = int(settings["encoder"]["encoder_button"])
encoder_left = int(settings["encoder"]["encoder_left"])
encoder_right = int(settings["encoder"]["encoder_right"])

# asyncio variables

loop = asyncio.get_event_loop()

# pathlib variables

default_path = Path(settings["settings"]["scripts_path"])

# pyudev variables

context = pyudev.Context()
monitor = pyudev.Monitor.from_netlink(context)

# custom characters
arrow = (
    0b00000,
    0b00100,
    0b00010,
    0b11111,
    0b00010,
    0b00100,
    0b00000,
    0b00000
)
back_arrow = (
    0b00100,
    0b01110,
    0b11111,
    0b00100,
    0b11100,
    0b00000,
    0b00000,
    0b00000
)
no_script = (
    0b00000,
    0b01111,
    0b10001,
    0b10001,
    0b10001,
    0b10001,
    0b11110,
    0b00000
)
script_running = (
    0b00000,
    0b01111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11110,
    0b00000
)
folder_char = (
    0b00000,
    0b11100,
    0b11111,
    0b10001,
    0b10001,
    0b11111,
    0b00000,
    0b00000
)
battery_empty = (
    0b00000,
    0b01110,
    0b11111,
    0b10011,
    0b10101,
    0b11001,
    0b11111,
    0b00000
)
battery_low = (
    0b00000,
    0b01110,
    0b11111,
    0b10001,
    0b10001,
    0b11111,
    0b11111,
    0b00000
)
battery_medium = (
    0b00000,
    0b01110,
    0b11111,
    0b10001,
    0b11111,
    0b11111,
    0b11111,
    0b00000
)
battery_full = (
    0b00000,
    0b01110,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b00000
)
usb_character = (
    0b00100,
    0b00101,
    0b10101,
    0b10110,
    0b01100,
    0b01110,
    0b00100,
    0b00000
)

# other variables

connection_index = 0
signal_status = 0
signal_stone = 0
signal_colour = 0
signal_count = 1
signal_gap_step = 0

signal_gap = 0.0

current_usb = ""

signal_status_list = ["all", "starter", "switch", "bridge", "sound", "lever"]
signal_stone_list = ["trigger", "finish", "starter", "controller", "bridge"]
signal_gap_step_list = [0.01, 0.05, 0.1, 0.5, 1.0]
connection_check_slots = []
info_check_slots = []
info_event_list = []
usb_slots = []

transfer = False
signal_sending = False
wait = True
wait2 = True
connection_result = False
update_available = False


# async functions


async def connect(index):
    global wait, connection_result, connection_index

    def disconnect_callback(bridge: gb.Bridge, **kwargs):
        if kwargs.get("user_disconnected"):
            pass
        else:
            if scripts[index] != "none":
                if modules[index].__name__ in sys.modules:
                    del sys.modules[modules[index].__name__]
                del modules[index]
                scripts[index] = "none"
            bridges_MAC[index] = "none"
            if GraviHub.current_menu == info_screen:
                info_event_list.append(f"C{index + 1} disconnected!")
            if connection_index == index and GraviHub.current_menu in [bridge_menu, script_selection_menu]:
                GraviHub.set(connections_menu)

    lcd.clear()
    lcd.cursor_pos = (1, 0)
    if settings["connections"][f"c{index}"] == "none":
        lcd.write_string("Connecting to:\r\nBridge...")
        if await bridges[index].connect(timeout=25, dc_callback=disconnect_callback):
            bridges_MAC[index] = bridges[index].get_address()
            for i in range(6):
                if settings["connections"][f"c{i}"] == bridges_MAC[index]:
                    bridges_MAC[index], bridges_MAC[i] = bridges_MAC[i], bridges_MAC[index]
                    bridges[index], bridges[i] = bridges[i], bridges[index]
                    index = i
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Connected to:\r\n{bridges_MAC[index]}!")
            await asyncio.sleep(3)
            wait = False
            connection_result = True
        else:
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Connecting Failed!")
            await asyncio.sleep(3)
            wait = False
    else:
        lcd.write_string(f"Connecting to:\r\n{settings['connections'][f'c{index}']}...")
        if await bridges[index].connect(timeout=25, dc_callback=disconnect_callback, by_name=False,
                                        name_or_addr=settings['connections'][f'c{index}']):
            bridges_MAC[index] = bridges[index].get_address()
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Connected to:\r\n{bridges_MAC[index]}!")
            await asyncio.sleep(3)
            wait = False
            connection_result = True
        else:
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Connecting Failed!")
            await asyncio.sleep(3)
            wait = False


async def lazy_connect(index: int) -> bool:
    global connection_index
    send = False

    def disconnect_callback(bridge: gb.Bridge, **kwargs):
        if kwargs.get("user_disconnected"):
            pass
        else:
            if scripts[index] != "none":
                if modules[index].__name__ in sys.modules:
                    del sys.modules[modules[index].__name__]
                del modules[index]
                scripts[index] = "none"
            bridges_MAC[index] = "none"
            if GraviHub.current_menu == info_screen:
                info_event_list.append(f"C{index + 1} disconnected!")
            if connection_index == index and GraviHub.current_menu in [bridge_menu, script_selection_menu]:
                GraviHub.set(connections_menu)

    if settings["connections"][f"c{index}"] == "none":
        if await bridges[index].connect(timeout=5, dc_callback=disconnect_callback):
            bridges_MAC[index] = bridges[index].get_address()
            for i in range(6):
                if settings["connections"][f"c{i}"] == bridges_MAC[index]:
                    bridges_MAC[index], bridges_MAC[i] = bridges_MAC[i], bridges_MAC[index]
                    bridges[index], bridges[i] = bridges[i], bridges[index]
                    connection_index = i
                    index = i
                if GraviHub.current_menu == info_screen and not send:
                    send = True
                    info_event_list.append(f"C{index + 1} connected!")
            return True
        else:
            return False
    else:
        if await bridges[index].connect(timeout=5, dc_callback=disconnect_callback, by_name=False,
                                        name_or_addr=settings['connections'][f'c{index}']):
            bridges_MAC[index] = bridges[index].get_address()
            if GraviHub.current_menu == info_screen:
                info_event_list.append(f"C{index + 1} connected!")
            return True
        else:
            return False


async def disconnect(index):
    global wait, connection_result
    lcd.clear()
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f"Disconnecting from:\r\n{bridges_MAC[index]}!")
    if await bridges[index].disconnect(timeout=25):
        lcd.clear()
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Disconnected from:\r\n{bridges_MAC[index]}!")
        bridges_MAC[index] = "none"
        if scripts[index] != "none":
            if modules[index].__name__ in sys.modules:
                del sys.modules[modules[index].__name__]
            del modules[index]
            scripts[index] = "none"
        await get_battery_levels()
        await asyncio.sleep(3)
        wait = False
        connection_result = True
    else:
        bridges_MAC[index] = bridges[index].get_address()
        lcd.clear()
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Disconnecting Failed")
        await asyncio.sleep(3)
        wait = False


async def lazy_disconnect(index):
    if await bridges[index].disconnect(timeout=5):
        bridges_MAC[index] = "none"
        if scripts[index] != "none":
            if modules[index].__name__ in sys.modules:
                del sys.modules[modules[index].__name__]
            del modules[index]
            scripts[index] = "none"
        return True
    else:
        bridges_MAC[index] = bridges[index].get_address()
        return False


async def send_signal():
    try:
        global signal_sending
        signal_sending = True
        if await bridges[await return_first_bridge(True)].send_periodic(
                stone=gc.DICT_STONE[signal_stone_list[signal_stone]],
                status=gc.DICT_STATUS[signal_status_list[
                    signal_status].upper()],
                color_channel=signal_colour, count=signal_count,
                gap=signal_gap):
            signal_sending = False
        signal_sending = False
    except gb.BleakError:
        signal_sending = False


async def toggle_bridge_mode(set_mode: bool) -> bool:
    global bridge_mode
    index = await return_first_bridge(True)
    if index is not False:
        if set_mode:
            await bridges[index].start_bridge_mode()
            bridge_mode = True
            return True
        else:
            await bridges[index].stop_bridge_mode()
            bridge_mode = False
            return True

    else:
        return False


async def disconnect_all():
    global wait2, connection_result
    lcd.clear()
    lcd.cursor_pos = (1, 0)
    lcd.write_string("Disconnecting All!")
    for i, bridge in enumerate(bridges):
        if await bridge.is_connected():
            while not await lazy_disconnect(i):
                time.sleep(0.5)
    lcd.cursor_pos = (1, 0)
    lcd.write_string("Done!               ")
    time.sleep(2)
    wait2 = False


async def return_first_bridge(connected: bool) -> int | bool:
    for i, bridge in enumerate(bridges):
        if connected:
            if await bridge.is_connected():
                return i
        else:
            if not await bridge.is_connected():
                return i
    return False


async def get_battery_levels():
    global battery_levels
    for i, bridge in enumerate(bridges):
        if await bridge.is_connected():
            battery_levels[i] = await bridge.request_battery()
            if battery_levels[i] is None:
                battery_levels[i] = 0
        else:
            battery_levels[i] = 0


# functions

def start_script(execute_file, index):
    global wait

    async def start():
        global wait
        if settings.getboolean("settings", "script_setup"):
            try:
                await (modules[index]).setup(bridges[index], bridge_count=bridge_count, wait=wait, lcd=lcd,
                                             connection_index=connection_index)
            except Exception as e:
                print(e)
        if await bridges[index].notification_enable((modules[index]).notification_callback):
            pass
        wait = False

    print(execute_file)
    spec = importlib.util.spec_from_file_location(execute_file.name, execute_file)
    print(type(importlib.util.module_from_spec(spec)))
    modules[index] = importlib.util.module_from_spec(spec)
    scripts[index] = execute_file.name
    spec.loader.exec_module(modules[index])
    print(dir(modules[index]))
    asyncio.run_coroutine_threadsafe(start(), loop)
    while wait:
        time.sleep(0.1)
        wait = False
    wait = True


def stop_script(index):
    global wait

    async def stop():
        global wait
        if settings.getboolean("settings", "script_shutdown"):
            try:
                await (modules[index]).shutdown(bridges[index], bridge_count=bridge_count, wait=wait, lcd=lcd,
                                                connection_index=connection_index)
            except Exception as e:
                print(e)
        if await bridges[index].notification_disable():
            pass
        wait = False

    asyncio.run_coroutine_threadsafe(stop(), loop)
    while wait:
        time.sleep(0.1)
    wait = True
    if modules[index].__name__ in sys.modules:
        del sys.modules[modules[index].__name__]
    del modules[index]
    scripts[index] = "none"


def usb_handler(action, device):
    if 'ID_FS_TYPE' in device:

        if action == "add":
            add_usb(device)

        if action == "remove":
            remove_usb(device)


def add_usb(device):
    print(type(device.get('ID_FS_LABEL')))
    if str(device.get('ID_FS_LABEL')) == "None":
        name = f"USB Drive"
    else:
        name = device.get('ID_FS_LABEL')

    usb_path = default_path / f"__usb-{name}_{device.device_node.replace('/', '_')}__"
    mount_path = str(usb_path).replace(' ', '\\ ')
    try:
        usb_path.mkdir()
    except FileExistsError:
        pass
    print(f"sudo mount -o uid=1000,gid=1000 {device.device_node} {usb_path}")
    os.system(f"sudo mount -o uid=1000,gid=1000 {device.device_node} {mount_path}")
    print(getpass.getuser())
    # os.system(f"sudo chown -R {getpass.getuser()} {mount_path}")
    usb_slots.insert(0, f"\x00#+#{name}#+##+#{device.device_node.replace('/', '_')}")
    if GraviHub.current_menu == info_screen:
        info_event_list.append(f"added USB: {name}")
    if isinstance(GraviHub.current_menu, MenuFile):
        while GraviHub.wait:
            time.sleep(0.01)
        GraviHub.current_menu.return_to_default()
        GraviHub.reset_menu()


def remove_usb(device):
    if str(device.get('ID_FS_LABEL')) == "None":
        name = f"USB Drive"

    else:
        name = device.get('ID_FS_LABEL')

    usb_path = default_path / f"__usb-{name}_{device.device_node.replace('/', '_')}__"
    os.system(f"sudo umount {device.device_node}")
    if str(script_selection_menu.current_path).startswith(str(usb_path)):
        script_selection_menu.return_to_default()
    index_list = []
    for key in modules:
        if str(modules[key].__file__).startswith(str(usb_path)):
            index_list.append(key)
    for index in index_list:
        if modules[index].__name__ in sys.modules:
            del sys.modules[modules[index].__name__]
        del modules[index]
        scripts[index] = "none"

    try:
        usb_path.rmdir()
    except FileNotFoundError:
        pass
    usb_slots.remove(f"\x00#+#{name}#+##+#{device.device_node.replace('/', '_')}")
    if GraviHub.current_menu == info_screen:
        info_event_list.append(f"removed USB: {name}")
    if isinstance(GraviHub.current_menu, MenuFile):
        while GraviHub.wait:
            time.sleep(0.01)
        GraviHub.current_menu.return_to_default()
        GraviHub.reset_menu()


def sd_to_usb(current_menu: RotaryMenu):
    global current_usb, transfer
    transfer = True
    pr_menu = current_menu.current_menu
    usb_dir = ""

    def move_files():
        try:
            from_dic = default_path
            to_dic = default_path / usb_dir
            index_list = []
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Starting Process!")
            time.sleep(1)
            for key in modules:
                if str(modules[key].__file__).startswith(str(to_dic)):
                    index_list.append(key)
            for index in index_list:
                if modules[index].__name__ in sys.modules:
                    del sys.modules[modules[index].__name__]
                del modules[index]
                scripts[index] = "none"
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Deleting:")
            time.sleep(0.1)
            for data in to_dic.iterdir():
                if data.is_dir() and not data.name.startswith("__"):
                    shutil.rmtree(data)
                    lcd.cursor_pos = (2, 0)
                    lcd.write_string(f"{data.name[:20] if len(data.name) > 20 else data.name.ljust(20, ' ')} ")
                    time.sleep(0.1)
                elif data.is_file():
                    data.unlink()
                    lcd.cursor_pos = (2, 0)
                    lcd.write_string(f"{data.name[:20] if len(data.name) > 20 else data.name.ljust(20, ' ')} ")
                    time.sleep(0.1)
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Copying:")
            time.sleep(0.1)
            for data in from_dic.iterdir():
                if data.is_dir() and not (data.name.startswith("__") or data.name == "System Volume Information"):
                    shutil.copytree(data, to_dic / data.name)
                    lcd.cursor_pos = (2, 0)
                    lcd.write_string(f"{data.name[:20] if len(data.name) > 20 else data.name.ljust(20, ' ')} ")
                    time.sleep(0.1)
                elif data.is_file():
                    shutil.copy(data, to_dic)
                    lcd.cursor_pos = (2, 0)
                    lcd.write_string(f"{data.name[:20] if len(data.name) > 20 else data.name.ljust(20, ' ')} ")
                    time.sleep(0.1)
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Done!")
            time.sleep(2)
        except Exception as e:
            print(e)

    def continue_menu_callback(callback_type, value, menu: RotaryMenu):
        global current_usb
        if callback_type == "setup":
            menu.max_index = 1
        if callback_type == "after_setup":
            print("hi")
            lcd.clear()
            lcd.cursor_pos = (0, 0)
            lcd.write_string("All files on the usb\r\n"
                             "Will be deleted.\r\n"
                             "Continue?\r\n"
                             ">yes  no")
        if callback_type == "direction":
            if value == "L":
                menu.index += 1
                menu.index = menu.index if menu.index <= 1 else 0
            else:
                menu.index -= 1
                menu.index = menu.index if menu.index >= 0 else 1
            lcd.cursor_pos = (3, 0 if menu.index == 0 else 5)
            lcd.write_string(">")
            lcd.cursor_pos = (3, 5 if menu.index == 0 else 0)
            lcd.write_string(" ")
        if callback_type == "press":
            if value == 0:
                current_usb = usb_dir
                move_files()
                menu.set(pr_menu)
            if value == 1:
                menu.set(pr_menu)

    continue_menu = MenuSub([], continue_menu_callback, do_setup_callback=True, after_reset_callback=True,
                            custom_cursor=True)

    def usb_selection_menu_callback(callback_type, value, menu: RotaryMenu):
        nonlocal usb_dir
        if callback_type == "setup":
            lcd.create_char(0, usb_character)
            lcd.create_char(2, back_arrow)
            usb_selection_menu.slots = ["#+#Back#+#\x02"]
            for slot in usb_slots:
                usb_selection_menu.slots.append(f"SD -> {slot}")
        if callback_type == "press":
            if value == 0:
                menu.set(pr_menu)
            if value > 0:
                slot = usb_selection_menu.slots[value].split("#+#")
                usb_dir = f"__usb-{slot[1]}_{slot[3]}__"
                print(usb_dir)
                menu.set(continue_menu)

    usb_selection_menu = MenuSub([], usb_selection_menu_callback, do_setup_callback=True)

    current_menu.set(usb_selection_menu)


def sd_from_usb(current_menu: RotaryMenu):
    global current_usb, transfer
    transfer = True
    pr_menu = current_menu.current_menu
    usb_dir = ""

    def move_files():
        try:
            from_dic = default_path / usb_dir
            to_dic = default_path
            index_list = []
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Starting Process!")
            time.sleep(1)
            for key in modules:
                if str(modules[key].__file__).startswith(str(to_dic)):
                    index_list.append(key)
            for index in index_list:
                if modules[index].__name__ in sys.modules:
                    del sys.modules[modules[index].__name__]
                del modules[index]
                scripts[index] = "none"
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Deleting:")
            time.sleep(0.1)
            for data in to_dic.iterdir():
                if data.is_dir() and not data.name.startswith("__"):
                    shutil.rmtree(data)
                    lcd.cursor_pos = (2, 0)
                    lcd.write_string(f"{data.name[:20] if len(data.name) > 20 else data.name.ljust(20, ' ')} ")
                    time.sleep(0.1)
                elif data.is_file():
                    data.unlink()
                    lcd.cursor_pos = (2, 0)
                    lcd.write_string(f"{data.name[:20] if len(data.name) > 20 else data.name.ljust(20, ' ')} ")
                    time.sleep(0.1)
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Copying:")
            time.sleep(0.1)
            for data in from_dic.iterdir():
                if data.is_dir() and not (data.name.startswith("__") or data.name == "System Volume Information"):
                    shutil.copytree(data, to_dic / data.name)
                    lcd.cursor_pos = (2, 0)
                    lcd.write_string(f"{data.name[:20] if len(data.name) > 20 else data.name.ljust(20, ' ')} ")
                    time.sleep(0.1)
                elif data.is_file():
                    shutil.copy(data, to_dic)
                    lcd.cursor_pos = (2, 0)
                    lcd.write_string(f"{data.name[:20] if len(data.name) > 20 else data.name.ljust(20, ' ')} ")
                    time.sleep(0.1)
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Done!")
            time.sleep(2)
        except Exception as e:
            print(e)

    def continue_menu_callback(callback_type, value, menu: RotaryMenu):
        global current_usb
        if callback_type == "setup":
            menu.max_index = 1
        if callback_type == "after_setup":
            print("hi")
            lcd.clear()
            lcd.cursor_pos = (0, 0)
            lcd.write_string("All current Scripts\r\n"
                             "Get deleted.\r\n"
                             "Continue?\r\n"
                             ">yes  no")
        if callback_type == "direction":
            if value == "L":
                menu.index += 1
                menu.index = menu.index if menu.index <= 1 else 0
            else:
                menu.index -= 1
                menu.index = menu.index if menu.index >= 0 else 1
            lcd.cursor_pos = (3, 0 if menu.index == 0 else 5)
            lcd.write_string(">")
            lcd.cursor_pos = (3, 5 if menu.index == 0 else 0)
            lcd.write_string(" ")
        if callback_type == "press":
            if value == 0:
                current_usb = usb_dir
                move_files()
                menu.set(pr_menu)
            if value == 1:
                menu.set(pr_menu)

    continue_menu = MenuSub([], continue_menu_callback, do_setup_callback=True, after_reset_callback=True,
                            custom_cursor=True)

    def usb_selection_menu_callback(callback_type, value, menu: RotaryMenu):
        nonlocal usb_dir
        if callback_type == "setup":
            lcd.create_char(0, usb_character)
            lcd.create_char(2, back_arrow)
            usb_selection_menu.slots = ["#+#Back#+#\x02"]
            for slot in usb_slots:
                usb_selection_menu.slots.append(f"SD <- {slot}")
        if callback_type == "press":
            if value == 0:
                menu.set(pr_menu)
            if value > 0:
                slot = usb_selection_menu.slots[value].split("#+#")
                usb_dir = f"__usb-{slot[1]}_{slot[3]}__"
                print(usb_dir)
                menu.set(continue_menu)

    usb_selection_menu = MenuSub([], usb_selection_menu_callback, do_setup_callback=True)

    current_menu.set(usb_selection_menu)


def check_for_updates():
    global update_available
    lcd.clear()
    lcd.cursor_pos = (1, 0)
    lcd.write_string("Searching updates...")
    time.sleep(2)
    try:
        new_update = requests.get("https://api.github.com/repos/FyrfyX8/GraviHub/releases/latest", timeout=5)
        if settings["about"]["version"] in new_update.json()["name"]:
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Updates found!      ")
        else:
            lcd.cursor_pos = (1, 0)
            lcd.write_string("No updates found!   ")
    except requests.ConnectionError:
        lcd.cursor_pos = (1, 0)
        lcd.write_string("No connection!")
    time.sleep(2)


def set_mac(index):
    with open("settings.ini", "w") as ini:
        settings.set("connections", f"c{index}", bridges_MAC[index])
        settings.write(ini)


def del_mac(index):
    with open("settings.ini", "w") as ini:
        settings.set("connections", f"c{index}", "none")
        settings.write(ini)


def return_dynamic_slots_to_str(slots: list):
    return_slots = []
    for slot in slots:
        return_slots.append(str(slot))
    return return_slots


# DynamicSlots Functions

def return_stone():
    return signal_stone_list[signal_stone]


def return_status():
    return signal_status_list[signal_status]


def return_color():
    return gc.LOOKUP_COLOR[signal_colour]


def return_count():
    return signal_count


def return_gap_step():
    return signal_gap_step_list[signal_gap_step]


def return_gap():
    return signal_gap


def return_battery_str(index):
    if float(battery_levels[index]) == 0.0:
        return "\x03"
    elif 2.0 <= float(battery_levels[index]) <= 2.5:
        return "\x04"
    elif float(battery_levels[index]) == 2.9:
        return "\x05"
    elif 3.0 <= float(battery_levels[index]) <= 3.1:
        return "\x06"


def return_setting(tab, setting):
    return settings[tab][setting]


def return_connection_name(index):
    if settings["connections"][f"c{index}"] == "none":
        return f"Connect{index + 1}"
    else:
        return settings["connections"][f"c{index}"]


def return_script_str(index, return_name=False):
    if return_name:
        if scripts[index] != "none":
            return Path(scripts[index]).name
        else:
            return ""
    else:
        if scripts[index] != "none":
            return "\x01"
        else:
            return "\x00"


def return_script(index):
    if scripts[index] != "none":
        return f"Stop:#+# {return_script_str(index, return_name=True)}#+#"
    else:
        return "#+#Start Script#+#\x03"


def return_mac_setting(index):
    if settings["connections"][f"c{index}"] == "none":
        return "Set MAC"
    else:
        return "Remove MAC"


def return_mac_str(index):
    return "/" if settings["connections"][f"c{index}"] == "none" else "M"


# Menus


def info_screen_callback(callback_type, value, menu):
    global connection_index, info_event_list
    if callback_type == "setup":
        async def auto_connect_handler():
            shift = 0
            while settings.getboolean("settings", "auto_connect") and menu.current_menu == info_screen:
                index = await return_first_bridge(False) + shift
                if settings.getboolean("settings", "auto_connect") is False or shift == 6:
                    break
                if await bridges[index].is_connected():
                    shift += 1
                else:
                    if await lazy_connect(index):
                        shift = 0
                    elif await lazy_connect(index) is False and settings["connections"][f"c{index}"] != "none":
                        shift += 1

        if settings.getboolean("settings", "auto_connect"):
            asyncio.run_coroutine_threadsafe(auto_connect_handler(), loop)
        connection_index = 10
        info_event_list = []
    if callback_type == "after_setup":
        async def info_screen_updater():
            lcd.clear()
            global info_check_slots, info_event_list
            info_countdown = 0
            shift = 0
            current_info_event = ""
            current_info_event_str = ""
            info_check_slots = []
            info = ""
            while menu.current_menu == info_screen:
                lcd.home()
                await get_battery_levels()
                updated_slots = []
                for i in range(6):
                    info += f"C{i + 1}{return_battery_str(i)}{return_script_str(i)}{return_mac_str(i)}"
                    info += "\r\n" if i == 2 or i == 5 else "  "
                    updated_slots.append(info)
                    info = ""
                if info_countdown == 0 and info_event_list:
                    pop = info_event_list.pop(0)
                    for i, entry in enumerate(info_event_list):
                        if entry == pop:
                            del info_event_list[i]
                    current_info_event = f"{' ' * 20}{pop}{' ' * 2}"
                    current_info_event_str = current_info_event[:20]
                    shift = 0
                    info_countdown = len(current_info_event)
                elif info_countdown > 0:
                    current_info_event_str = current_info_event[0 + shift: 20 + shift]
                    shift += 1
                    info_countdown -= 1
                elif not info_event_list:
                    current_info_event_str = "GraviHub idle..."
                updated_slots.append(current_info_event_str + "\r\n")
                if info_check_slots != updated_slots:
                    while menu.wait:
                        await asyncio.sleep(0.01)
                    if menu.current_menu != info_screen:
                        break
                    menu.wait = True
                    for entry in updated_slots:
                        lcd.write_string(entry)
                    menu.wait = False
                info_check_slots = updated_slots
                await asyncio.sleep(0.1)

        lcd.create_char(0, no_script)
        lcd.create_char(1, script_running)
        lcd.create_char(3, battery_empty)
        lcd.create_char(4, battery_low)
        lcd.create_char(5, battery_medium)
        lcd.create_char(6, battery_full)
        lcd.home()
        asyncio.run_coroutine_threadsafe(info_screen_updater(), loop)
    if callback_type == "press":
        lcd.clear()
        menu.set(selection_menu)


info_screen = MenuMain(["#+##+#"], info_screen_callback, do_setup_callback=True, after_reset_callback=True,
                       custom_cursor=True)

selection_menu_slots = ["#+#Info Screen#+#\x03", "#+#Connections#+#\x02", "#+#Bridge Mode#+#[Off]",
                        "#+#Settings#+#\x02", "#+#Manage Files#+#\x02"]


def selection_menu_callback(callback_type, value, menu):
    global wait
    if callback_type == "setup":
        lcd.clear()
        lcd.create_char(2, arrow)
        lcd.create_char(3, back_arrow)
    if callback_type == "press":
        if value == 0:
            menu.set(info_screen)
        elif value == 1:
            menu.set(connections_menu)
        elif value == 2:

            async def toggle_mode():
                global wait
                if bridge_mode:
                    if await toggle_bridge_mode(False):
                        selection_menu.change_slot(2, "#+#Bridge Mode#+#[Off]")
                        menu.update_current_slot()
                    else:
                        lcd.clear()
                        lcd.cursor_pos = (1, 0)
                        lcd.write_string("No Bridge Connected!")
                        time.sleep(2)
                        menu.reset_menu()

                else:
                    if await toggle_bridge_mode(True):
                        selection_menu.change_slot(2, "#+#Bridge Mode#+#[On]")
                        menu.update_current_slot()
                    else:
                        lcd.clear()
                        lcd.cursor_pos = (1, 0)
                        lcd.write_string("No Bridge Connected!")
                        time.sleep(2)
                        lcd.clear()
                        menu.reset_menu()
                wait = False

            asyncio.run_coroutine_threadsafe(toggle_mode(), loop)
            while wait:
                time.sleep(0.01)
            wait = True

        elif value == 3:
            menu.set(settings_menu)

        elif value == 4:
            if usb_slots:
                menu.set(fmm_selection_menu)
            else:
                lcd.clear()
                lcd.cursor_pos = (1, 0)
                lcd.write_string("No usb drives found!")
                time.sleep(2)
                menu.reset_menu()


selection_menu = MenuSub(selection_menu_slots, selection_menu_callback, do_setup_callback=True)

fmm_selection_menu_slots = ["#+#Main Menu#+#\x03", "#+#SD -> \x04USB#+#\x02", "#+#SD <- \x04USB#+#\x02"]


def fmm_selection_menu_callback(callback_type, value, menu):
    if callback_type == "setup":
        lcd.create_char(2, arrow)
        lcd.create_char(3, back_arrow)
        lcd.create_char(4, usb_character)
    if callback_type == "press":
        if value == 0:
            GraviHub.set(selection_menu)
        if value == 1:
            sd_to_usb(menu)
        if value == 2:
            sd_from_usb(menu)


fmm_selection_menu = MenuSub(fmm_selection_menu_slots, fmm_selection_menu_callback, do_setup_callback=True)

connections_menu_slots = ["#+#Main Menu#+#\x02",
                          DynamicSlot("#+#{c}#+#{b}{s}", c=return_connection_name, c_args=(0,),
                                      b=return_battery_str, b_args=(0,), s=return_script_str, s_args=(0,)),
                          DynamicSlot("#+#{c}#+#{b}{s}", c=return_connection_name, c_args=(1,),
                                      b=return_battery_str, b_args=(1,), s=return_script_str, s_args=(1,)),
                          DynamicSlot("#+#{c}#+#{b}{s}", c=return_connection_name, c_args=(2,),
                                      b=return_battery_str, b_args=(2,), s=return_script_str, s_args=(2,)),
                          DynamicSlot("#+#{c}#+#{b}{s}", c=return_connection_name, c_args=(3,),
                                      b=return_battery_str, b_args=(3,), s=return_script_str, s_args=(3,)),
                          DynamicSlot("#+#{c}#+#{b}{s}", c=return_connection_name, c_args=(4,),
                                      b=return_battery_str, b_args=(4,), s=return_script_str, s_args=(4,)),
                          DynamicSlot("#+#{c}#+#{b}{s}", c=return_connection_name, c_args=(5,),
                                      b=return_battery_str, b_args=(5,), s=return_script_str, s_args=(5,))
                          ]


def connections_menu_callback(callback_type, value, menu):
    global connection_index, wait, connection_result

    async def connections_menu_update_handler():
        global connection_check_slots
        while menu.current_menu == connections_menu:
            await get_battery_levels()
            updated_slots = return_dynamic_slots_to_str(connections_menu_slots)
            if connection_check_slots != updated_slots:
                while menu.wait:
                    await asyncio.sleep(0.01)
                menu.wait = True
                menu.menu()
                menu.wait = False
            connection_check_slots = updated_slots
            await asyncio.sleep(0.5)

    if callback_type == "setup":
        lcd.clear()
        lcd.create_char(0, no_script)
        lcd.create_char(1, script_running)
        lcd.create_char(2, back_arrow)
        lcd.create_char(3, battery_empty)
        lcd.create_char(4, battery_low)
        lcd.create_char(5, battery_medium)
        lcd.create_char(6, battery_full)
        asyncio.run_coroutine_threadsafe(connections_menu_update_handler(), loop)
        connection_index = 10
    if callback_type == "press":
        if value == 0:
            menu.set(selection_menu)
        if 1 <= value <= 6:
            connection_index = value - 1
            if bridges_MAC[connection_index] == "none":
                asyncio.run_coroutine_threadsafe(connect(connection_index), loop)
                while wait:
                    time.sleep(0.01)
                wait = True
                if connection_result:
                    connection_result = False
                    menu.set(bridge_menu)
                else:
                    menu.reset_menu()
            else:
                menu.set(bridge_menu)


connections_menu = MenuSub(connections_menu_slots, connections_menu_callback, do_setup_callback=True)

bridge_menu_slots = ["#+#Back#+#\x02",
                     DynamicSlot("{s}", s=return_script, s_args=(connection_index,)),
                     DynamicSlot("#+#{MAC}#+#", MAC=return_mac_setting,
                                 MAC_args=(connection_index,)),
                     "#+#Disconnect#+#\x02"]


def bridge_menu_callback(callback_type, value, menu):
    global wait, connection_result
    if callback_type == "setup":
        lcd.clear()
        lcd.create_char(3, arrow)
        bridge_menu_slots[1].function_args["s_args"] = (connection_index,)
        bridge_menu_slots[2].function_args["MAC_args"] = (connection_index,)

        print(scripts)
        print(connection_index)
    if callback_type == "press":
        if value == 0:
            menu.set(connections_menu)
        elif value == 1:
            if scripts[connection_index] == "none":
                menu.set(script_selection_menu)
            else:
                stop_script(connection_index)
                menu.update_current_slot()
        elif value == 2:
            if settings["connections"][f"c{connection_index}"] == "none":
                set_mac(connection_index)
            else:
                del_mac(connection_index)
            menu.update_current_slot()
        elif value == 3:
            asyncio.run_coroutine_threadsafe(disconnect(connection_index), loop)
            while wait:
                time.sleep(0.01)
            wait = True
            if connection_result:
                connection_result = False
                menu.set(connections_menu)
            else:
                menu.reset_menu()


bridge_menu = MenuSub(bridge_menu_slots, bridge_menu_callback, do_setup_callback=True)

script_selection_menu_pr_slots = ["#+#Back#+#\x02"]


def script_selection_menu_callback(callback_type, value, menu):
    global wait
    if callback_type == "setup":
        lcd.clear()
        lcd.create_char(0, usb_character)
        lcd.create_char(1, folder_char)
        script_selection_menu.fmd0_slots = usb_slots
    if callback_type == "press":
        if value == 0:
            menu.set(bridge_menu)
        elif script_selection_menu.slots[value].startswith("\x00"):
            slot = script_selection_menu.slots[value].split('#+#')
            usb_directory = f"__usb-{slot[1]}_{slot[3]}__"
            if (script_selection_menu.current_path / usb_directory).exists():
                script_selection_menu.move_to_dir(usb_directory)
                menu.reset_menu()
    if callback_type == "file_press":
        start_script(value, connection_index)
        menu.set(bridge_menu)


script_selection_menu = MenuFile(default_path, script_selection_menu_callback, pr_slots=script_selection_menu_pr_slots,
                                 dir_affix="\x01#+#", do_setup_callback=True)

settings_menu_slots = ["#+#Main Menu#+#\x03", "#+#Send Signals#+#\x02",
                       DynamicSlot("#+#Script Setup#+#[{rs}]", rs=return_setting, rs_args=("settings", "script_setup")),
                       DynamicSlot("#+#Script Shutdown#+#[{rs}]", rs=return_setting,
                                   rs_args=("settings", "script_shutdown")),
                       DynamicSlot("#+#Auto Connect#+#[{rs}]", rs=return_setting, rs_args=("settings", "auto_connect")),
                       "#+#Remove all MAC#+#", "#+#Disconnect all#+#", "#+#No Updates#+#", "#+#Network Settings#+#\x02",
                       "#+#About#+#\x02"]


def settings_menu_callback(callback_type, value, menu):
    global wait2
    if callback_type == "setup":
        if update_available:
            selection_menu.change_slot(8, "#+#New Update#+#\x02")
        else:
            print("got")
    if callback_type == "press":
        if value == 0:
            menu.set(selection_menu)
        elif value == 1:
            if asyncio.run(return_first_bridge(True)) is not False:
                menu.set(send_signal_menu)
            else:
                lcd.clear()
                lcd.cursor_pos = (1, 0)
                lcd.write_string("No Bridge Connected!")
                time.sleep(2)
                menu.reset_menu()
        elif value == 2:
            with open("settings.ini", "w") as ini:
                if settings.getboolean("settings", "script_setup"):
                    settings.set("settings", "script_setup", "Off")
                else:
                    settings.set("settings", "script_setup", "On")
                settings.write(ini)
            menu.update_current_slot()
        elif value == 3:
            with open("settings.ini", "w") as ini:
                if settings.getboolean("settings", "script_shutdown"):
                    settings.set("settings", "script_shutdown", "Off")
                else:
                    settings.set("settings", "script_shutdown", "On")
                settings.write(ini)
            menu.update_current_slot()
        elif value == 4:
            with open("settings.ini", "w") as ini:
                if settings.getboolean("settings", "auto_connect"):
                    settings.set("settings", "auto_connect", "Off")
                else:
                    settings.set("settings", "auto_connect", "On")
                settings.write(ini)
            menu.update_current_slot()
        elif value == 5:
            for i in range(len(bridges_MAC)):
                del_mac(i)
        elif value == 6:
            asyncio.run_coroutine_threadsafe(disconnect_all(), loop)
            while wait2:
                time.sleep(0.01)
            wait2 = True
            menu.reset_menu()
        elif value == 7:
            pass
        elif value == 8:
            menu.set(wlan_settings_menu)
        elif value == 9:
            menu.set(about_menu)


settings_menu = MenuSub(settings_menu_slots, settings_menu_callback, do_setup_callback=True)

wlan_settings_menu = MenuNetworkSettings(Path("/etc/netplan/50-cloud-init.yaml"), back_arrow, arrow)


def about_menu_callback(callback_type, value, menu):
    if callback_type == "after_setup":
        lcd.clear()
        lcd.home()
        lcd.write_string(f"GraviHub v.{settings['about']['version']}\r\n")

        def get_mac(interface):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes(interface, 'utf-8')[:15]))
            return ':'.join('%02x' % b for b in info[18:24]).upper()

        lcd.write_string(f"{get_mac('wlan0')}\r\n")
        lcd.write_string("Made by FyrfyX8\r\n")
        lcd.write_string("More info on GitHub!")


    if callback_type == "press":
        menu.set(settings_menu)


about_menu = MenuSub([], about_menu_callback, do_setup_callback=True, after_reset_callback=True, custom_cursor=True)


send_signal_menu_slots = ["#+#Back#+#\x03",
                          DynamicSlot("#+#Stone#+#[{rst}]", rst=return_stone),
                          DynamicSlot("#+#Status#+#[{rstat}]", rstat=return_status),
                          DynamicSlot("#+#Colour#+#[{rcl}]", rcl=return_color),
                          DynamicSlot("#+#Count#+#[{rct}]", rct=return_count),
                          DynamicSlot("#+#Gap step#+#[{rgps}]", rgps=return_gap_step),
                          DynamicSlot("#+#Gap#+#[{rgp}]", rgp=return_gap),
                          "#+#Send Signal#+#\x02"]


def send_signal_menu_callback(callback_type, value, menu):
    global signal_stone, signal_status, signal_colour, signal_count, signal_gap_step, signal_gap
    if callback_type == "setup":
        send_signal_menu.custom_cursor = False
    if callback_type == "direction":
        if menu.index == 1:
            signal_stone = signal_stone + 1 if value == "L" else signal_stone - 1
            signal_stone = len(signal_stone_list) - 1 if signal_stone < 0 \
                else 0 if len(signal_stone_list) <= signal_stone else signal_stone
        elif menu.index == 2:
            signal_status = signal_status + 1 if value == "L" else signal_status - 1
            signal_status = len(signal_status_list) - 1 if signal_status < 0 \
                else 0 if len(signal_status_list) <= signal_status else signal_status
        elif menu.index == 3:
            signal_colour = signal_colour + 1 if value == "L" else signal_colour - 1
            signal_colour = 3 if signal_colour < 1 else 1 if 3 < signal_colour \
                else signal_colour
        elif menu.index == 4:
            signal_count = signal_count + 1 if value == "L" else signal_count - 1
            signal_count = 1 if signal_count < 1 else signal_count
        elif menu.index == 5:
            signal_gap_step = signal_gap_step + 1 if value == "L" else signal_gap_step - 1
            signal_gap_step = len(signal_gap_step_list) - 1 if signal_gap_step < 0 \
                else 0 if len(signal_gap_step_list) <= signal_gap_step else signal_gap_step
        elif menu.index == 6:
            signal_gap = signal_gap + signal_gap_step_list[signal_gap_step] if value == "L" \
                else signal_gap - signal_gap_step_list[signal_gap_step]
            signal_gap = 0.0 if signal_gap < 0.0 else signal_gap
            signal_gap = round(signal_gap, 2)
        menu.update_current_slot()
    if callback_type == "press":
        if value == 0:
            menu.set(settings_menu)
        elif 0 < value < 7:
            if send_signal_menu.custom_cursor:
                send_signal_menu.custom_cursor = False
            else:
                send_signal_menu.custom_cursor = True
        elif value == 7:
            print(signal_sending)
            if not signal_sending:
                asyncio.run_coroutine_threadsafe(send_signal(), loop)
            else:
                lcd.clear()
                lcd.cursor_pos = (1, 0)
                lcd.write_string("Must clear first!")
                time.sleep(2)
                menu.reset_menu()


send_signal_menu = MenuSub(send_signal_menu_slots, send_signal_menu_callback, do_setup_callback=True)

GraviHub = RotaryMenu(right_pin=encoder_right, left_pin=encoder_left, button_pin=encoder_button, main=info_screen,
                      menu_timeout=30)

# menu_update_handler


if __name__ == "__main__":
    try:
        monitor.filter_by('block')
        observer = pyudev.MonitorObserver(monitor, usb_handler)

        lcd.cursor_pos = (1, 0)
        lcd.write_string("Welcome to GraviHub!\r\n")
        time.sleep(0.5)
        loading_usb = 0
        for device in context.list_devices(subsystem='block', DEVTYPE='partition'):
            print('{0} ({1})'.format(device.device_node, device.get('ID_FS_TYPE')))
            if 'ID_FS_TYPE' in device:
                if device.device_node.startswith("/dev/sd"):
                    loading_usb += 1
        if loading_usb <= 0:
            pass
        else:
            if loading_usb == 1:
                lcd.write_string("loading 1 USB-Drive\r\n")
            else:
                lcd.write_string(f"loading {loading_usb} USB-Drives\r\n")
            for device in context.list_devices(subsystem='block', DEVTYPE='partition'):
                print('{0} ({1})'.format(device.device_node, device.get('ID_FS_TYPE')))
                if 'ID_FS_TYPE' in device:
                    if device.device_node.startswith("/dev/sd"):
                        add_usb(device)

        time.sleep(2)
        check_for_updates()
        time.sleep(2)
        lcd.home()
        lcd.clear()
        observer.start()
        GraviHub.set()
        loop.run_forever()
    except KeyboardInterrupt:
        for device in context.list_devices(subsystem='block', DEVTYPE='partition'):
            print('{0} ({1})'.format(device.device_node, device.get('ID_FS_TYPE')))
            if 'ID_FS_TYPE' in device:
                if device.device_node.startswith("/dev/sd"):
                    remove_usb(device)
        lcd.close(clear=True)
        GPIO.cleanup()
        loop.stop()
