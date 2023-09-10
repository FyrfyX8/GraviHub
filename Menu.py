import time
import json

from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
from time import sleep
import asyncio
from gravitraxconnect import gravitrax_bridge as gb
from encoder import Encoder

GPIO.setmode(GPIO.BCM)

buttonPin = 27

GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

CursorPos = 0
MenuIndex = 0
MacAdresses = ["new"]
SlotsMM = ["add new Connection"]
SlotsCM = ["Main Menu","Start Skript","Disconnect","Delete Connection"]
MainMenu = [SlotsMM, MacAdresses]
MenuDeph = 0
def valueChanged(value, direction):
    global MenuIndex, CursorPos, CursorPrPos
    CursorPrPos = CursorPos
    if direction == "L" :
        CursorPos -= 1
    else:
        CursorPos += 1

    if CursorPos == -1:
        CursorPos = 0
        MenuIndex -=1
    elif CursorPos == 4:
        CursorPos = 3
        MenuIndex += 1
    if CursorPos == CursorPrPos:
        pass
    else:
        Cursor(CursorPrPos)

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
sleep(2)
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
        json.dump(["1", "2", "3"], Connections)


previous_button_state = GPIO.input(buttonPin)

def puttonPress():
    global MenuIndex
    button_state = GPIO.input(buttonPin)
    if button_state != previous_button_state:
        previous_button_state = button_state
        if button_state == GPIO.HIGH:
            print("Pressed")
            return MenuIndex

def Cursor(CursorPrPos):
    global CursorPos
    lcd.cursor_pos = (CursorPos, 0)
    lcd.write_string(">")
    lcd.cursor_pos = (CursorPrPos, 0)
    lcd.write_string(" ")

def ResetCursor():
    global CursorPos
    CursorPrPos = CursorPos
    CursorPos = 0
    Cursor(CursorPrPos)

lcd.clear()
Cursor(1)

while True:
    pass