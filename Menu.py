import time
from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
import asyncio
from gravitraxconnect import gravitrax_bridge as gb
from encoder import Encoder
import json

lcd = CharLCD(i2c_expander="PCF8574", address=0x27, port=1, cols=20, rows=4, dotsize=8)
GPIO.setmode(GPIO.BCM)

buttonPin = 27

CursorPos = 0
MenuIndex = 0
MenuMMIndex = 0
MenuMaxIndex = 0
MenuPos = 0
MenuMaxPos = 0
MenuDeph = 0

SlotsMM = ["Connection1", "Connection2", "Connection3", "Connection4", "Connection5", "Connection6"]
MacAdresses = []
Scripts = ["none", "none", "none", "none", "none", "none"]
SlotsCM = ["Main Menu", "Start Script", "Set Mac-Adress",]
SlotsFM = ["Back"]

ButtonEnabled = True
RotateEnabled = True
Wait = True

bridge = gb.Bridge()


# CustomCarakters
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
no_skript = (
    0b00000,
    0b01111,
    0b10001,
    0b10001,
    0b10001,
    0b10001,
    0b11110,
    0b00000
)
skript_running = (
    0b00000,
    0b01111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11110,
    0b00000
)


def ReadMA():
    global MacAdresses
    try:
        with open("Connections.json", "r") as Connections:
            MacAdresses = json.load(Connections)
        print(MacAdresses)
        Connections.close()
    except FileNotFoundError:
        with open("Connections.json", "w") as Connections:
            MacAdresses = ["none", "none", "none", "none", "none", "none"]
            json.dump(MacAdresses, Connections)
            Connections.close()


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


def Menu():
    global MenuDeph, SlotsCM, SlotsMM, MenuPos, MenuMaxIndex, Scripts, MenuMMIndex
    CurrentSlots = ["none", "none", "none", "none"]
    if MenuDeph == 0:
        CurrentSlots = SlotsMM
    elif MenuDeph == 1:
        CurrentSlots = SlotsCM
    MenuLenght(CurrentSlots)
    CurrentIndex = MenuPos
    CurrentRow = 0
    for i in range(4):
        try:
            if MenuDeph == 1 and CurrentIndex == 3:
                lcd.write_string(MacAdresses[MenuMMIndex])

            lcd.cursor_pos = (CurrentRow, 1)
            if len(CurrentSlots[CurrentIndex]) >= 17:
                lcd.write_string(slice(CurrentSlots[CurrentIndex], 0, 17))
            else:
                lcd.write_string(CurrentSlots[CurrentIndex] + " " * (17 - len(CurrentSlots[CurrentIndex])))
            if MenuDeph == 0:
                if Scripts[CurrentIndex] == "none":
                    lcd.write_string("\x02\x00")
                else:
                    lcd.write_string("\x03\x00")
            if MenuDeph == 1:
                if CurrentIndex == 0:
                    lcd.write_string(" \x01")
                else:
                    lcd.write_string(" \x00")

            CurrentRow += 1
            CurrentIndex += 1
        except Exception:
            pass


def ResetMenu():
    global MenuIndex, MenuPos, RotateEnabled, ButtonEnabled
    lcd.clear()
    MenuIndex = 0
    MenuPos = 0
    ResetCursor()
    Menu()
    time.sleep(0.1)
    RotateEnabled = True
    ButtonEnabled = True


async def SetMac():
    async def Disconnect():
        lcd.clear()
        lcd.cursor_pos = (1, 3)
        lcd.write_string("Disconnecting!")
        if await bridge.disconnect(timeout=25):
            pass

        else:
            await Disconnect()
    try:
        global MacAdresses, MenuMMIndex, Wait
        lcd.clear()
        lcd.cursor_pos = (1, 0)
        lcd.write_string("Connecting To Bridge")
        if await bridge.connect(timeout=2):
            lcd.cursor_pos = (1, 0)
            MacAdress = bridge.get_address()
            lcd.write_string("Connectet To Bridge!\r\nMac{0}".format(MacAdress))
            del MacAdresses[MenuMMIndex]
            MacAdresses.insert(MenuMMIndex, MacAdress)
            with open("Connections.json", "w") as Connections:
                json.dump(MacAdresses, Connections)
                Connections.close()
            await asyncio.sleep(3)
            await Disconnect()
        else:
            lcd.cursor_pos = (1, 0)
            lcd.write_string("No Connection found!")
    except Exception:
        lcd.cursor_pos = (1, 0)
        lcd.write_string("No Connection found!")
        await asyncio.sleep(2)
    finally:
        Wait = False
        ResetMenu()
        loop.close()
def RemoveMac():
    global MacAdresses, MenuMMIndex
    lcd.clear()
    lcd.cursor_pos = (1, 4)
    lcd.write_string("Removing Mac")
    del MacAdresses[MenuMMIndex]
    MacAdresses.insert(MenuMMIndex, "none")
    with open("Connections.json", "w") as Connections:
        json.dump(MacAdresses, Connections)
        Connections.close()
    time.sleep(1)
    lcd.clear()
    lcd.cursor_pos = (1, 7)
    lcd.write_string("Done!")
    ResetMenu()


def buttonPress(arg):
    global MenuDeph, MenuIndex, MenuMaxIndex, MacAdresses, MenuMMIndex, RotateEnabled, ButtonEnabled, Wait

    if ButtonEnabled and Wait:
        MenuPrDeph = MenuDeph

        ButtonEnabled = False
        RotateEnabled = False
    if MenuDeph == 0:
        MenuMMIndex = MenuIndex
        MenuDeph = 1
    elif MenuDeph == 1:
        if MenuIndex == 0:
            MenuDeph = 0
        elif MenuIndex == 2:
            if MacAdresses[MenuMMIndex] == "none":
                asyncio.run_coroutine_threadsafe(SetMac(), loop)
                while Wait:
                    time.sleep(0.01)
                Wait = True
            elif MacAdresses[MenuMMIndex] != "none":
                RemoveMac()

    if MenuDeph != MenuPrDeph:
        ResetMenu()
    else:
        time.sleep(0.1)
        ButtonEnabled = True
        RotateEnabled = True


def valueChanged(value, direction):
    global MenuPos, CursorPos, MenuMaxPos, MenuIndex
    CursorPrPos = CursorPos
    MenuPrPos = MenuPos
    if RotateEnabled and Wait:
        if direction == "R":
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
                MenuPos -= 1
        elif CursorPos == 4:
            CursorPos = 3
            if MenuPos != MenuMaxPos:
                MenuPos += 1
        if CursorPos != CursorPrPos:
            Cursor(CursorPrPos)
        if MenuPos != MenuPrPos:
            Menu()

        print(CursorPos, MenuIndex)


loop = asyncio.get_event_loop()

if __name__ == "__main__":
    try:
        e1 = Encoder(4, 17, valueChanged)

        GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(buttonPin, GPIO.RISING, callback=buttonPress, bouncetime=1200)

        lcd.create_char(0, arrow)
        lcd.create_char(1, back_arrow)
        lcd.create_char(2, no_skript)
        lcd.create_char(3, skript_running)

        lcd.clear()
        lcd.cursor_pos = (1, 0)
        lcd.write_string('Welcome to GraviHub!')
        ReadMA()
        time.sleep(3)
        lcd.clear()
        Cursor(1)
        Menu()
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        lcd.close(clear=True)
        GPIO.cleanup()
        loop.stop()

