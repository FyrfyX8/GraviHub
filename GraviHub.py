from RotaryMenu import *
from gravitraxconnect import gravitrax_bridge as gb
from gravitraxconnect import gravitrax_constants as gc
from RPLCD.i2c import CharLCD
from configparser import ConfigParser
from pathlib import Path

import sys
import time
import RPi.GPIO as GPIO
import asyncio
import importlib.util
import pyudev
import os

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

default = Path(settings["settings"]["scripts_path"])

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

connection_check_slots = []
info_check_slots = []
info_event_list = []

wait = True
wait2 = True
connection_result = False


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
                info_event_list.append(f"C{index} connected!")
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
        if await bridge.is_connected() is connected:
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

    usb_path = default / f"__usb-{name}_{device.device_node.replace('/', '_')}__"
    mount_path = str(usb_path).replace(' ', '\\ ')
    try:
        usb_path.mkdir()
    except FileExistsError:
        pass
    print(f"sudo mount {device.device_node} {usb_path}")
    os.system(f"sudo mount {device.device_node} {mount_path}")
    script_selection_menu.fmd0_slots.insert(script_selection_menu.pr_slots_last_index,
                                            f"\x00#+#{name}#+##+#{device.device_node.replace('/', '_')}")
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

    usb_path = default / f"__usb-{name}_{device.device_node.replace('/', '_')}__"
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
    script_selection_menu.fmd0_slots.remove(f"\x00#+#{name}#+##+#{device.device_node.replace('/', '_')}")
    if GraviHub.current_menu == info_screen:
        info_event_list.append(f"removed USB: {name}")
    if isinstance(GraviHub.current_menu, MenuFile):
        while GraviHub.wait:
            time.sleep(0.01)
        GraviHub.current_menu.return_to_default()
        GraviHub.reset_menu()


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
                    current_info_event = f"{' '*20}{pop}{' '* 2}"
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
                        lcd.clear()
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


selection_menu = MenuSub(selection_menu_slots, selection_menu_callback, do_setup_callback=True)

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


script_selection_menu = MenuFile(default, script_selection_menu_callback, pr_slots=script_selection_menu_pr_slots,
                                 dir_affix="\x01#+#", do_setup_callback=True)

settings_menu_slots = ["#+#Main Menu#+#\x03", "#+#Send Signals#+#\x02",
                       DynamicSlot("#+#Script Setup#+#[{rs}]", rs=return_setting, rs_args=("settings", "script_setup")),
                       DynamicSlot("#+#Script Shutdown#+#[{rs}]", rs=return_setting,
                                   rs_args=("settings", "script_shutdown")),
                       DynamicSlot("#+#Auto Connect#+#[{rs}]", rs=return_setting, rs_args=("settings", "auto_connect")),
                       "#+#Remove all MAC#+#", "#+#Disconnect all#+#", ]


def settings_menu_callback(callback_type, value, menu):
    global wait2
    if callback_type == "setup":
        pass
    if callback_type == "press":
        if value == 0:
            menu.set(selection_menu)
        elif value == 1:
            pass
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


settings_menu = MenuSub(settings_menu_slots, settings_menu_callback, do_setup_callback=True)

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

        time.sleep(3)
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
