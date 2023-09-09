from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
from time import sleep
import asyncio
from gravitraxconnect import gravitrax_bridge as gb
from encoder import Encoder

e1 = Encoder(4,17)
bridge = gb.Bridge()

MacAdresses = ["new"]
SlotsMM = ["add new Connection"]
SlotsCM = ["Main Menu","Start Skript","Disconnect","Delete Connection"]
MainMenu = [SlotsMM, MacAdresses]
MenuDeph = 0
CursorPos = 0
MenuIndex = 0

lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=20, rows=4, dotsize=8)
lcd.clear()

lcd.cursor_pos = (2, 0)
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

while 1 == 1 :
    if MenuDeph == 0:

