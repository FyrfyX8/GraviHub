import sys
import RPi.GPIO as GPIO
from gravitraxconnect import gravitrax_bridge as gb
from RotaryMenu.RotaryMenuClasses import *
from configparser import ConfigParser
from pathlib import Path
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

unnamed_usb_sticks = ["None", "None", "None", "None"]
pr_slots = []

wait = True
connection_result = False
active = False


# async functions

async def connect(index):
    global wait, connection_result

    def disconnect_callback(bridge: gb.Bridge, **kwargs):
        if kwargs.get("user_disconnected"):
            pass
        else:
            if modules[index].__name__ in sys.modules:
                del sys.modules[modules[index].__name__]
            del modules[index]
            bridges_MAC[index] = "none"
            if connection_index == index:
                GraviHub.set(connections_menu)
            print("hahd")

    lcd.clear()
    lcd.cursor_pos = (1, 0)
    if settings["connections"][f"c{index}"] == "none":
        lcd.write_string("Connecting to:\r\nBridge...")
        if await bridges[index].connect(timeout=25, dc_callback=disconnect_callback):
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
    print("kakj")


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
        scripts[index] = "none"
        await get_battery_levels()
        await asyncio.sleep(3)
        wait = False
        connection_result = True
    else:
        lcd.clear()
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Disconnecting Failed")
        await asyncio.sleep(3)
        wait = False


async def return_first_bridge():
    index = 0
    for bride in bridges:
        if await bride.is_connected():
            return index
        else:
            index += 1


async def get_battery_levels():
    global battery_levels
    index = 0
    for bridge in bridges:
        if await bridge.is_connected():
            battery_levels[index] = await bridge.request_battery()
            if battery_levels[index] is None:
                battery_levels[index] = 0
        else:
            battery_levels[index] = 0
        index += 1


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
        for i in range(len(unnamed_usb_sticks)):
            if unnamed_usb_sticks[i] == "None":
                unnamed_usb_sticks[i] = device.device_node
                name = f"USB Drive {i + 1}"
                break
    else:
        for i in range(len(unnamed_usb_sticks), 0):
            if unnamed_usb_sticks[i] == "None":
                unnamed_usb_sticks[i] = device.device_node
                break
        name = device.get('ID_FS_LABEL')

    usb_path = default / f"__usb-{name}__"
    mount_path = str(usb_path).replace(' ', '\\ ')
    try:
        usb_path.mkdir()
    except FileExistsError:
        pass
    print(f"sudo mount {device.device_node} {usb_path}")
    os.system(f"sudo mount {device.device_node} {mount_path}")
    script_selection_menu.fmd0_slots.insert(script_selection_menu.pr_slots_last_index, f"\x00#+#{name}#+#")
    if isinstance(GraviHub.current_menu, MenuFile):
        while GraviHub.wait:
            time.sleep(0.01)
        GraviHub.current_menu.return_to_default()
        GraviHub.reset_menu()


def remove_usb(device):
    if str(device.get('ID_FS_LABEL')) == "None":
        for i in range(len(unnamed_usb_sticks)):
            if unnamed_usb_sticks[i] == device.device_node:
                unnamed_usb_sticks[i] = "None"
                name = f"USB Drive {i + 1}"
                break
    else:
        for i in range(len(unnamed_usb_sticks)):
            if unnamed_usb_sticks[i] == device.device_node:
                unnamed_usb_sticks[i] = "None"
                break
        name = device.get('ID_FS_LABEL')

    usb_path = default / f"__usb-{name}__"
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
    script_selection_menu.fmd0_slots.remove(f"\x00#+#{name}#+#")
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

def return_DynamicSlots_to_str(slots: list):
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


def return_MAC(index):
    if settings["connections"][f"c{index}"] == "none":
        return "Set MAC"
    else:
        return "Remove MAC"


# Menus


def info_screen_callback(callback_type, value):
    global connection_index
    if callback_type == "setup":
        connection_index = 10
    if callback_type == "after_setup":
        lcd.create_char(0, no_script)
        lcd.create_char(1, script_running)
        lcd.create_char(3, battery_empty)
        lcd.create_char(4, battery_low)
        lcd.create_char(5, battery_medium)
        lcd.create_char(6, battery_full)
        lcd.home()
        lcd.write_string("C1\x03\x00/  C2\x03\x00/  C3\x03\x00/ \r\n" +
                         "C4\x03\x00/  C5\x03\x00/  C6\x03\x00/ \r\n" +
                         "GraviHub Idle.\r\n")
        if bridge_mode:
            lcd.write_string("Bridge Mode: On")
        else:
            lcd.write_string("bridge Mode: Off")
    if callback_type == "press":
        lcd.clear()
        GraviHub.set(selection_menu)


info_screen = MenuMain(["#+##+#"], info_screen_callback, do_setup_callback=True, after_reset_callback=True,
                       custom_cursor=True)

selection_menu_slots = ["#+#Info Screen#+#\x03", "#+#Connections#+#\x02", "#+#Bridge Mode#+#[Off]",
                        "#+#Settings#+#\x02", "#+#Manage Files#+#\x02"]


def selection_menu_callback(callback_type, value):
    global bridge_mode
    if callback_type == "setup":
        lcd.clear()
        lcd.create_char(2, arrow)
        lcd.create_char(3, back_arrow)
    if callback_type == "press":
        if value == 0:
            GraviHub.set(info_screen)
        elif value == 1:
            GraviHub.set(connections_menu)
        elif value == 2:
            if bridge_mode:
                selection_menu.change_slot(2, "#+#Bridge Mode#+#[Off]")
                bridge_mode = False
            else:
                selection_menu.change_slot(2, "#+#Bridge Mode#+#[On]")
                bridge_mode = True
            print(selection_menu.slots)
            GraviHub.update_current_slot()
        elif value == 3:
            GraviHub.set(settings_menu)


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


def connections_menu_callback(callback_type, value):
    global connection_index, wait, connection_result

    async def connections_menu_update_handler():
        global pr_slots
        while GraviHub.current_menu == connections_menu:
            await get_battery_levels()
            if pr_slots != return_DynamicSlots_to_str(connections_menu_slots):
                while GraviHub.wait:
                    await asyncio.sleep(0.01)
                GraviHub.wait = True
                GraviHub.menu()
                GraviHub.wait = False
            pr_slots = return_DynamicSlots_to_str(connections_menu_slots)
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
            GraviHub.set(selection_menu)
        if value > 0:
            connection_index = value - 1
            if bridges_MAC[connection_index] == "none":
                asyncio.run_coroutine_threadsafe(connect(connection_index), loop)
                while wait:
                    time.sleep(0.01)
                wait = True
                if connection_result:
                    connection_result = False
                    GraviHub.set(bridge_menu)
                else:
                    GraviHub.reset_menu()
            else:
                GraviHub.set(bridge_menu)


connections_menu = MenuSub(connections_menu_slots, connections_menu_callback, do_setup_callback=True)

bridge_menu_slots = ["#+#Back#+#\x02",
                     DynamicSlot("{s}", s=return_script, s_args=(connection_index,)),
                     DynamicSlot("#+#{MAC}#+#", MAC=return_MAC,
                                 MAC_args=(connection_index,)),
                     "#+#Disconnect#+#\x02"]


def bridge_menu_callback(callback_type, value):
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
            GraviHub.set(connections_menu)
        elif value == 1:
            if scripts[connection_index] == "none":
                GraviHub.set(script_selection_menu)
            else:
                stop_script(connection_index)
                GraviHub.update_current_slot()
        elif value == 2:
            if settings["connections"][f"c{connection_index}"] == "none":
                set_mac(connection_index)
            else:
                del_mac(connection_index)
            GraviHub.update_current_slot()
        elif value == 3:
            asyncio.run_coroutine_threadsafe(disconnect(connection_index), loop)
            while wait:
                time.sleep(0.01)
            wait = True
            if connection_result:
                connection_result = False
                GraviHub.set(connections_menu)
            else:
                GraviHub.reset_menu()


bridge_menu = MenuSub(bridge_menu_slots, bridge_menu_callback, do_setup_callback=True)

script_selection_menu_pr_slots = ["#+#Back#+#\x02"]


def script_selection_menu_callback(callback_type, value):
    global wait
    if callback_type == "setup":
        lcd.clear()
        lcd.create_char(0, usb_character)
        lcd.create_char(1, folder_char)
    if callback_type == "press":
        usb_directory = f"__usb-{script_selection_menu.slots[value].split('#+#', 2)[1]}__"
        if value == 0:
            GraviHub.set(bridge_menu)
        if (script_selection_menu.current_path / usb_directory).exists():
            script_selection_menu.move_to_dir(usb_directory)
            GraviHub.reset_menu()
    if callback_type == "file_press":
        start_script(value, connection_index)
        GraviHub.set(bridge_menu)


script_selection_menu = MenuFile(default, script_selection_menu_callback, pr_slots=script_selection_menu_pr_slots,
                                 dir_affix="\x01#+#", do_setup_callback=True)

settings_menu_slots = ["#+#Main Menu#+#\x03", "#+#Send Signals#+#\x02",
                       DynamicSlot("#+#Script Setup#+#[{rs}]", rs=return_setting, rs_args=("settings", "script_setup")),
                       DynamicSlot("#+#Script Shutdown#+#[{rs}]", rs=return_setting,
                                   rs_args=("settings", "script_shutdown")),
                       "#+#Remove all MAC#+#", "#+#Disconnect all#+#", ]


def settings_menu_callback(callback_type, value):
    if callback_type == "setup":
        pass
    if callback_type == "press":
        if value == 0:
            GraviHub.set(selection_menu)
        elif value == 1:
            pass
        elif value == 2:
            with open("settings.ini", "w") as ini:
                if settings.getboolean("settings", "script_setup"):
                    settings.set("settings", "script_setup", "Off")
                else:
                    settings.set("settings", "script_setup", "On")
                settings.write(ini)
            GraviHub.update_current_slot()
        elif value == 3:
            with open("settings.ini", "w") as ini:
                if settings.getboolean("settings", "script_shutdown"):
                    settings.set("settings", "script_shutdown", "Off")
                else:
                    settings.set("settings", "script_shutdown", "On")
                settings.write(ini)
            GraviHub.update_current_slot()
        elif value == 4:
            for i in range(len(bridges_MAC)):
                del_mac(i)




settings_menu = MenuSub(settings_menu_slots, settings_menu_callback, do_setup_callback=True)

GraviHub = RotaryMenu(right_pin=encoder_right, left_pin=encoder_left, button_pin=encoder_button, main=info_screen,
                      menu_timeout=30)

# menu_update_handler


if __name__ == "__main__":

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

    GraviHub.set(info_screen)

    try:
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
