import time

from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
from time import sleep
import asyncio
from gravitraxconnect import gravitrax_bridge as gb
from encoder import Encoder

GPIO.setmode(GPIO.BCM)

buttonPin = 27

GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


CursorPos: int = 0
MenuIndex = 0
def valueChanged(value, direction):
    global MenuIndex, CursorPos

    if direction == "L" :
        CursorPos -= 1

    else:
        CursorPos += 1
    print(CursorPos)

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
    with open("Connections.txt","r") as Connections:
        for line in Connections:
            SlotsMM.insert(-1,"Connecton "+ line.strip())
        for I in SlotsMM:
            if I == "add new Connection":
                pass
            else:
                MacAdresses.insert(0,"none")
        print(SlotsMM)
        print(MacAdresses)
except FileNotFoundError:
    print("Connections.txt does not exist creating new one!")
    with open("Connections.txt", "x"):
        pass

previous_button_state = GPIO.input(buttonPin)

while 1 == 1 :
    if MenuDeph == 0:
        time.sleep(0.01)
        button_state = GPIO.input(buttonPin)
        if button_state != previous_button_state :
           previous_button_state = button_state
           if button_state == GPIO.HIGH :
               print("Released")
        lcd.write_string('Placeholder!')