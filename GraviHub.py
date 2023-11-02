import time
from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
import asyncio
from gravitraxconnect import gravitrax_bridge as gb
from RotaryMenu import RotaryMenuClasses
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

# RMC Renaming for better usage
RotaryMenu = RotaryMenuClasses.RotaryMenu
MenuMain = RotaryMenuClasses.Main
MenuSub = RotaryMenuClasses.Sub
MenuFile = RotaryMenuClasses.File

# Variables for the Bridges
mac_addresses = [settings["connections"]["c1"], settings["connections"]["c2"], settings["connections"]["c3"],
                 settings["connections"]["c4"], settings["connections"]["c5"], settings["connections"]["c6"]]
bridges = [gb.Bridge(), gb.Bridge(), gb.Bridge(), gb.Bridge(), gb.Bridge(), gb.Bridge()]
battery_levels = [0, 0, 0, 0, 0, 0]
scripts = ["none", "none", "none", "none", "none", "none"]
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
    0b01110,
    0b00101,
    0b10101,
    0b10110,
    0b01100,
    0b00100,
    0b00000
)

# other variables

connection_index = 0
# Menus


def info_screen_callback(callback_type, value):
    if callback_type == "after_setup":
        lcd.create_char(0, no_script)
        lcd.create_char(1, script_running)
        lcd.create_char(2, battery_empty)
        lcd.create_char(3, battery_low)
        lcd.create_char(4, battery_medium)
        lcd.create_char(5, battery_full)
        lcd.home()
        lcd.write_string("C1\x02\x00/  C2\x02\x00/  C3\x02\x00/ \r\n" +
                         "C4\x02\x00/  C5\x02\x00/  C6\x02\x00/ \r\n" +
                         "GraviHub Idle.\r\n")
        if bridge_mode:
            lcd.write_string("Bridge Mode: On")
        else:
            lcd.write_string("bridge Mode: Off")
        active = True
    if callback_type == "press":
        lcd.clear()
        GraviHub.set(selection_menu)


info_screen = MenuMain(["#+##+#"], info_screen_callback, after_reset_callback=True, custom_cursor=True)

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

connections_menu_slots = ["#+#Main Menu#+#\x02", "#+#Connection1#+#\x03\x00", "#+#Connection2#+#\x03\x00",
                          "#+#Connection3#+#\x03\x00", "#+#Connection4#+#\x03\x00", "#+#Connection5#+#\x03\x00",
                          "#+#Connection6#+#\x03\x00"]

def connections_menu_callback(callback_type, value):
    if callback_type == "setup":
        lcd.clear()
        lcd.create_char(2, back_arrow)
        lcd.create_char(3, battery_empty)
        lcd.create_char(4, battery_low)
        lcd.create_char(5, battery_medium)
        lcd.create_char(6, battery_full)
    if callback_type == "press":
        if value == 0:
            GraviHub.set(selection_menu)
        if value > 0:
            print(value - 1)
            GraviHub.set(bridge_menu)

connections_menu = MenuSub(connections_menu_slots, connections_menu_callback, do_setup_callback=True)

bridge_menu_slots = ["#+#MainMenu#+#\x02", "#+#Back#+#\x02", "#+#Start Script#+#\x03", "#+#Set MAC#+#\x03",
                     "#+#Disconnect#+#\x02"]

def bridge_menu_callback(callback_type, value):
    if callback_type == "setup":
        lcd.clear()
        lcd.create_char(3, arrow)
    if callback_type == "press":
        if value == 0:
            GraviHub.set(selection_menu)
        elif value == 1:
            GraviHub.set(connections_menu)
        elif value == 2:
            GraviHub.set(script_selection_menu)


bridge_menu = MenuSub(bridge_menu_slots, bridge_menu_callback, do_setup_callback=True)

script_selection_menu_pr_slots = ["#+#Back#+#\x02"]

def script_selection_menu_callback(callback_type, value):
    if callback_type == "setup":
        lcd.clear()
        lcd.create_char(0, usb_character)
        lcd.create_char(1, folder_char)
    if callback_type == "press":
        if value == 0:
            GraviHub.set(bridge_menu)

script_selection_menu = MenuFile(default, script_selection_menu_callback, pr_slots=script_selection_menu_pr_slots,
                                 dir_affix="\x01#+#", do_setup_callback=True)

settings_menu_slots = ["#+#Main Menu#+#\x03","#+#Send Signals#+#\x02", "#+#Show USB#+#[Off]", "#+#Script Setup#+#[Off]",
                       "#+#Script Shutdown#+#[Off]"]

def settings_menu_callback(callback_type, value):
    if callback_type == "setup":
        pass
    if callback_type == "press":
        if value == 0:
            GraviHub.set(selection_menu)

settings_menu = MenuSub(settings_menu_slots, settings_menu_callback, do_setup_callback=True)

GraviHub = RotaryMenu(right_pin=encoder_right, left_pin=encoder_left, button_pin=encoder_button, main=info_screen,
                      menu_timeout=30)

# async functions


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
            battery_levels.pop(index)
            battery_levels.insert(index, await bridge.request_battery())
        else:
            battery_levels.pop(index)
            battery_levels.insert(index, 0)

# functions

def usb_handler(action, device):
    global usb_paths
    if 'ID_FS_TYPE' in device:

        if action == "add":
            add_usb(device)

        if action == "remove":
            remove_usb(device)

def add_usb(device):
    if device.get('ID_FS_LABEL') == "none":
        name = "USB Drive"
    else:
        name = device.get('ID_FS_LABEL')

    usb_path = default / f"__usb-{name}__"
    try:
        usb_path.mkdir()
    except FileExistsError:
        pass
    os.system(f"sudo mount {device.device_node} {usb_path}")
    script_selection_menu.fmd0_slots.insert(script_selection_menu.pr_slots_last_index, f"\x00#+#{name}#+#")
    if isinstance(GraviHub.current_menu, MenuFile):
        while GraviHub.wait:
            time.sleep(0.01)
        GraviHub.current_menu.return_to_default()
        GraviHub.reset_menu()

def remove_usb(device):
    if device == "none":
        name = "USB Drive"
    else:
        name = device.get('ID_FS_LABEL')

    usb_path = default / f"__usb-{name}__"
    os.system(f"sudo umount {device.device_node}")
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


if __name__ == "__main__":

    monitor.filter_by('block')
    observer = pyudev.MonitorObserver(monitor, usb_handler)


    lcd.cursor_pos = (1, 0)
    lcd.write_string("Welcome to GraviHub!\r\n")
    time.sleep(0.5)
    lcd.write_string(" loading USB-Drives \r\n")
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