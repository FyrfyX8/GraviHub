import time
import json

from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
from time import sleep
import asyncio
from gravitraxconnect import gravitrax_bridge as gb
from encoder import Encoder

def puttonPress(arg):
    print("Pressed")


GPIO.setmode(GPIO.BCM)

buttonPin = 27

GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(buttonPin, GPIO.RISING, callback=puttonPress, bouncetime=200)

CursorPos = 0
MenuIndex = 0
MenuMaxIndex = 0
MenuPos = 0
MenuMaxPos = 0
MacAdresses = ["new"]
SlotsMM = ["add new Connection"]
SlotsCM = ["Main Menu","Start Skript","Disconnect","Delete Connection"]
MainMenu = [SlotsMM, MacAdresses]
MenuDeph = 0
def valueChanged(value, direction):
    global MenuPos, CursorPos, MenuMaxPos, MenuIndex
    CursorPrPos = CursorPos
    MenuPrPos = MenuPos

    if direction == "L" :
        if MenuIndex != 0:
            CursorPos -= 1
            MenuIndex -= 1
    else:
        if MenuIndex != MenuMaxIndex:
            CursorPos += 1
            MenuIndex += 1

    if CursorPos == -1:
        CursorPos = 0
        if MenuPos != 0:
            MenuPos -=1
    elif CursorPos == 4:
        CursorPos = 3
        if MenuPos != MenuMaxPos:
            MenuPos += 1
    if CursorPos != CursorPrPos:
        Cursor(CursorPrPos)
    if MenuPos != MenuPrPos:
        Menu()

    print(CursorPos, MenuIndex)

e1 = Encoder(4,17, valueChanged)
bridge = gb.Bridge()

MacAdresses = ["new"]
SlotsMM = ["add new Connection"]
SlotsCM = ["Main Menu","Start Skript","Disconnect","Delete Connection"]
MainMenu = [SlotsMM, MacAdresses]
MenuDeph = 0

lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=20, rows=4, dotsize=8)
lcd.clear()

lcd.cursor_pos = (1, 0)
lcd.write_string('Welcome to GraviHub!')
sleep(5)
try:
    with open("Connections.json","r") as Connections:
        json_str = json.load(Connections)
        for I in reversed(json_str):
            SlotsMM.insert(0, I)

        for I in SlotsMM:
            if I == "add new Connection":
                pass
            else:
                MacAdresses.insert(0,"none")
        print(SlotsMM)
        print(MacAdresses)
except FileNotFoundError:
    print("Connections.json does not exist creating new one!")
    with open("Connections.json", "w") as Connections:
        json.dump(["Connection1", "Connection2", "Connection3"], Connections)


previous_button_state = GPIO.input(buttonPin)

def Cursor(CursorPrPos):
    global CursorPos
    lcd.cursor_pos = (CursorPrPos, 0)
    lcd.write_string(" ")
    lcd.cursor_pos = (CursorPos, 0)
    lcd.write_string(">")

def ResetCursor():
    global CursorPos
    CursorPrPos = CursorPos
    CursorPos = 0
    Cursor(CursorPrPos)

def MenuLenght(MenuType):
    global MenuMaxIndex, MenuMaxPos
    MenuMaxIndex = len(MenuType) - 1
    MenuMaxPos = MenuMaxIndex - 3
    print("Menu Lenght: ", MenuMaxIndex,", Max Pos: ", MenuMaxPos)

def Menu():
    global MenuDeph, SlotsCM, SlotsMM, MenuPos
    if MenuDeph == 0:
        CurrentSlots = SlotsMM
    elif MenuDeph == 1:
        CurrentSlots = SlotsCM
    else:
        pass
    MenuLenght(CurrentSlots)
    CurrentIndex = MenuPos
    CurrentRow = 0
    lcd.clear()
    for i in range(4):
        lcd.cursor_pos = (CurrentRow, 1)
        CurrentRow += 1
        lcd.write_string(CurrentSlots[CurrentIndex])
        CurrentIndex += 1
    Cursor(0)

lcd.clear()
Cursor(1)
Menu()

while True:
    time.sleep(0.01)