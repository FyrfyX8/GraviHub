import time
from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
import asyncio
from gravitraxconnect import gravitrax_bridge as gb
from encoder import Encoder
import json
from pathlib import Path
import importlib.util

# GraviHub V.1

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
MenuPrDeph = 0
FMenuDeph = 2
BridgeCount = 0


ConfScripts = Path("/home/fnorb/GraviHub/Scripts")
CurrentPath = ConfScripts
ConnectionPath = Path("/home/fnorb/GraviHub/Connections.json")

SlotsMM = ["Connection1", "Connection2", "Connection3", "Connection4", "Connection5", "Connection6"]
MacAddresses = []
Scripts = ["none", "none", "none", "none", "none", "none"]
SlotsCM = ["Main Menu", "Start Script", "Set Mac-Address",]
SlotsFM = ["Connection Menu"]
CurrentSlots = SlotsMM

ButtonEnabled = True
RotateEnabled = True
Wait = False
Connection = False
DisEvent = False
RollingEvent = False
RollingFlag = True
bridge = gb.Bridge()
bridges = [gb.Bridge(), gb.Bridge(), gb.Bridge(), gb.Bridge(), gb.Bridge(), gb.Bridge()]


# CustomCaracters
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


def ReadMA():
    global MacAddresses, ConfPath
    try:
        with ConnectionPath.open("r") as Connections:
            MacAddresses = json.load(Connections)
        Connections.close()
    except FileNotFoundError:
        with ConnectionPath.open("w") as Connections:
            MacAddresses = ["none", "none", "none", "none", "none", "none"]
            json.dump(MacAddresses, Connections)
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

def GetFiles():
    global SlotsFM, CurrentPath, MenuDeph
    if MenuDeph == 2:
        SlotsFM = ["Connection Menu"]
    else:
        SlotsFM = ["Connection Menu", "\x04.."]
    for folder in CurrentPath.iterdir():
        if folder.is_dir() and not folder.name.startswith("__"):
            SlotsFM.append("\x04"+folder.name)
    for file in CurrentPath.glob("*.py"):
        SlotsFM.append(file.name)





def MenuLength(MenuType):
    global MenuMaxIndex, MenuMaxPos
    MenuMaxIndex = len(MenuType) - 1
    MenuMaxPos = MenuMaxIndex - 3


def Menu():
    global MenuDeph, SlotsCM, SlotsMM, SlotsFM, MenuPos, MenuMaxIndex, Scripts, MenuMMIndex, CurrentSlots
    CurrentSlots = ["none", "none", "none", "none"]
    if MenuDeph == 0:
        CurrentSlots = SlotsMM
    elif MenuDeph == 1:
        CurrentSlots = SlotsCM
        if Scripts[MenuMMIndex] != "none":
            del CurrentSlots[1]
            CurrentSlots.insert(1, f"Stop Script       {Scripts[MenuMMIndex]}")
        else:
            del CurrentSlots[1]
            CurrentSlots.insert(1, "Start Script")
        if MacAddresses[MenuMMIndex] != "none":
            del CurrentSlots[2]
            CurrentSlots.insert(2, "Del Mac-Address")
        else:
            del CurrentSlots[2]
            CurrentSlots.insert(2, "Set Mac-Address")

    elif MenuDeph >= 2:
        GetFiles()
        CurrentSlots = SlotsFM
    MenuLength(CurrentSlots)
    CurrentIndex = MenuPos
    CurrentRow = 0
    for i in range(4):
        try:
            if MenuDeph == 1 and CurrentIndex == 3:
                lcd.write_string(MacAddresses[MenuMMIndex])
            lcd.cursor_pos = (CurrentRow, 1)
            if len(CurrentSlots[CurrentIndex]) >= 19 and MenuDeph >= 2:
                lcd.write_string(CurrentSlots[CurrentIndex][0: 19])
            elif len(CurrentSlots[CurrentIndex]) >= 16:
                lcd.write_string(CurrentSlots[CurrentIndex][0: 16])
            elif MenuDeph >= 2:
                lcd.write_string(CurrentSlots[CurrentIndex] + " " * (18 - len(CurrentSlots[CurrentIndex])))
            else:
                lcd.write_string(CurrentSlots[CurrentIndex] + " " * (16 - len(CurrentSlots[CurrentIndex])))
            if MenuDeph == 0:
                if MacAddresses[CurrentIndex] == "none":
                    lcd.write_string(" ")
                else:
                    lcd.write_string("M")
                if Scripts[CurrentIndex] == "none":
                    lcd.write_string("\x02\x00")
                else:
                    lcd.write_string("\x03\x00")
            if MenuDeph == 1:
                if CurrentIndex == 0:
                    lcd.write_string("  \x01")
                else:
                    lcd.write_string("  \x00")
            if MenuDeph >= 2:
                if CurrentIndex == 0:
                    lcd.write_string("\x01")
                else:
                    lcd.write_string(" ")


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


async def Run(spec, Module, MacAddress):
    global MenuMMIndex, Wait, Connection, bridges
    spec.loader.exec_module(Module)
    index = MenuMMIndex

    def disconnect_callback(bridge: gb.Bridge, **kwargs):
        global Wait, Scripts
        if kwargs.get("user_disconnected"):
            del Scripts[index]
            Scripts.insert(index, "none")
        else:
            Wait = False
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Connection{index} timeout!")
            time.sleep(2)
            del Scripts[index]
            Scripts.insert(index, "none")
            ResetMenu()
            Wait = True
    async def Disconnect():
        global Wait, BridgeCount
        lcd.clear()
        lcd.cursor_pos = (1, 3)
        lcd.write_string("Disconnecting!")
        try:
            await Module.GBshutdown(bridges[MenuMMIndex], BridgeCount)
        except Exception as e:
            print(e)
        if await bridges[MenuMMIndex].disconnect(timeout=25):
            Wait = False
            BridgeCount -= 1
        else:
            await Disconnect()
    async def main():
        global Wait, DisEvent, BridgeCount

        BridgeCount += 1

        try:
            await Module.GBsetup(bridges[MenuMMIndex], BridgeCount)
        except Exception as e:
            print(e)
        if await bridges[MenuMMIndex].notification_enable(Module.notification_callback):
            pass
        while True:
            if DisEvent and index == MenuMMIndex:
                break
            else:
                await asyncio.sleep(0.01)
        DisEvent = False
        await Disconnect()

    try:
        if MacAddress != "none":
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Connecting to\r\n   {MacAddress}")
            if await bridges[MenuMMIndex].connect(name_or_addr=MacAddress, timeout=25, by_name=False,
                                                  dc_callback=disconnect_callback):
                lcd.clear()
                lcd.cursor_pos = (1, 0)
                lcd.write_string("Connected to Bridge!")
                await asyncio.sleep(2)
                Connection = True
                Wait = False
                await main()
            else:
                lcd.clear()
                lcd.cursor_pos = (1, 0)
                lcd.write_string("No Connection found!")
                await asyncio.sleep(2)
                Wait = False

        else:
            lcd.clear()
            lcd.cursor_pos = (1, 0)
            lcd.write_string("Connecting to Bridge")
            if await bridges[MenuMMIndex].connect(timeout=25, dc_callback=disconnect_callback):
                lcd.clear()
                lcd.cursor_pos = (1, 0)
                lcd.write_string("Connected to Bridge!")
                await asyncio.sleep(2)
                Connection = True
                Wait = False
                await main()
            else:
                lcd.cursor_pos = (1, 0)
                lcd.write_string("No Connection found!")
                await asyncio.sleep(2)
                Wait = False

    except Exception as e:
        print(e)
        Wait = False


def Start(ExecuteFile):
    global MenuMMIndex, Scripts, MacAddresses, MenuDeph, FMenuDeph, Wait, Connection
    spec = importlib.util.spec_from_file_location(ExecuteFile.name[:-3], ExecuteFile)
    Module = importlib.util.module_from_spec(spec)
    asyncio.run_coroutine_threadsafe(Run(spec, Module, MacAddresses[MenuMMIndex]), loop)
    while Wait:
        time.sleep(0.01)
    Wait = True
    if Connection:
        del Scripts[MenuMMIndex]
        Scripts.insert(MenuMMIndex, ExecuteFile.name)
        FMenuDeph = MenuDeph
        MenuDeph = 1
    else:
        ResetMenu()
    Connection = False


def Stop():
    global MenuMMIndex, Wait, Scripts, DisEvent

    DisEvent = True
    while Wait:
        time.sleep(0.01)
    Wait = True
    ResetMenu()


def FMN():
    global MenuDeph, MenuIndex, CurrentPath, SlotsFM
    if MenuDeph >= 3 and MenuIndex == 1:
        MenuDeph -= 1
        CurrentPath = CurrentPath.parent
    else:
        TempPath = CurrentPath / SlotsFM[MenuIndex].replace("\x04", "")
        if TempPath.is_file():
            Start(TempPath)
        elif TempPath.is_dir():
            CurrentPath = TempPath
            MenuDeph += 1


async def SetMac():
    global MacAddresses, MenuMMIndex, Wait
    async def Disconnect():
        global Wait
        lcd.clear()
        lcd.cursor_pos = (1, 3)
        lcd.write_string("Disconnecting!")
        if await bridge.disconnect(timeout=25):
            ResetMenu()
            Wait = False
        else:
            await Disconnect()
    if Scripts[MenuMMIndex] != "none":
        lcd.clear()
        lcd.cursor_pos = (1, 0)
        lcd.write_string("Scipt is running,\r\n       can't set Mac")
        await asyncio.sleep(1)
        ResetMenu()
        Wait = False
        return

    try:
        lcd.clear()
        lcd.cursor_pos = (1, 0)
        lcd.write_string("Connecting To Bridge")
        if await bridge.connect(timeout=25):
            lcd.cursor_pos = (1, 0)
            MacAddress = bridge.get_address()
            lcd.write_string("Connectet To Bridge!")
            del MacAddresses[MenuMMIndex]
            MacAddresses.insert(MenuMMIndex, MacAddress)
            with ConnectionPath.open("w") as Connections:
                json.dump(MacAddresses, Connections)
                Connections.close()
            await asyncio.sleep(3)
            await Disconnect()
        else:
            lcd.cursor_pos = (1, 0)
            lcd.write_string("No Connection found!")
            await asyncio.sleep(2)
            ResetMenu()
            Wait = False
    except Exception as e:
        print(e)


def RemoveMac():
    global MacAddresses, MenuMMIndex
    if Scripts[MenuMMIndex] != "none":
        lcd.clear()
        lcd.cursor_pos = (1, 0)
        lcd.write_string("Scipt is running,\r\n       can't del Mac")
        time.sleep(1)
        ResetMenu()
        return
    lcd.clear()
    lcd.cursor_pos = (1, 4)
    lcd.write_string("Removing Mac")
    del MacAddresses[MenuMMIndex]
    MacAddresses.insert(MenuMMIndex, "none")
    with ConnectionPath.open("w") as Connections:
        json.dump(MacAddresses, Connections)
        Connections.close()
    time.sleep(1)
    lcd.clear()
    lcd.cursor_pos = (1, 7)
    lcd.write_string("Done!")
    ResetMenu()


async def Rolling():
    global MenuIndex, CurrentSlots, CursorPos, RollingEvent, Wait, RollingFlag

    MenuPrIndex = MenuIndex
    shift = 0
    for times in range(100):
        if MenuIndex != MenuPrIndex or not ButtonEnabled:
            return
        else:
            await asyncio.sleep(0.01)
    RollingEvent = True
    if MenuDeph <= 1:
        for i in range(len(CurrentSlots[MenuIndex]) - 17):
            if not RollingEvent:
                RollingFlag = False
                return
            lcd.cursor_pos = (CursorPos, 1)
            lcd.write_string(CurrentSlots[MenuIndex][shift:shift + 18])
            await asyncio.sleep(0.01)
            shift += 1
            for times in range(20):
                if not RollingEvent:
                    RollingFlag = False
                    return
                else:
                    await asyncio.sleep(0.01)

    elif CurrentSlots[MenuIndex].startswith("\x04"):
        shift = 1
        for i in range(len(CurrentSlots[MenuIndex]) - 18):
            if not RollingEvent:
                RollingFlag = False
                return
            lcd.cursor_pos = (CursorPos, 2)
            lcd.write_string(CurrentSlots[MenuIndex][shift:shift + 18])
            await asyncio.sleep(0.01)
            shift += 1
            for times in range(20):
                if not RollingEvent:
                    RollingFlag = False
                    return
                else:
                    await asyncio.sleep(0.01)
    else:
        for i in range(len(CurrentSlots[MenuIndex]) - 18):
            if not RollingEvent:
                RollingFlag = False
                return
            lcd.cursor_pos = (CursorPos, 1)
            lcd.write_string(CurrentSlots[MenuIndex][shift:shift + 19])
            await asyncio.sleep(0.01)
            shift += 1
            for times in range(20):
                if not RollingEvent:
                    RollingFlag = False
                    return
                else:
                    await asyncio.sleep(0.01)
    while True:
        if not RollingEvent:
            RollingFlag = False
            return
        else:
            await asyncio.sleep(0.01)


def ResetRolling(index, row):
    global RollingEvent, RollingFlag
    RollingEvent = False
    while RollingFlag:
        time.sleep(0.01)
    RollingFlag = True
    lcd.cursor_pos = (row, 1)
    if MenuDeph == 1:
        lcd.write_string(CurrentSlots[index][0:16] + "  ")
    else:
        lcd.write_string(CurrentSlots[index][0:19])


def buttonPress(arg):
    global ButtonEnabled, Wait

    def pressed():
        global MenuDeph, FMenuDeph, MenuIndex, MenuMaxIndex, MacAddresses, MenuMMIndex, RotateEnabled, ButtonEnabled, Wait, \
            Scripts, MenuPrDeph, RollingEvent, RollingFlag, Connecting

        if ButtonEnabled and Wait:
            MenuPrDeph = MenuDeph
            if RollingEvent:
                ResetRolling(MenuIndex, CursorPos)

            ButtonEnabled = False
            RotateEnabled = False
            # MainMenu
            if MenuDeph == 0:
                MenuMMIndex = MenuIndex
                MenuDeph = 1
            # ConnectionMenu
            elif MenuDeph == 1:
                if MenuIndex == 0:
                    MenuDeph = 0
                elif MenuIndex == 1:
                    if Scripts[MenuMMIndex] != "none":
                        Stop()
                    else:
                        MenuDeph = FMenuDeph
                elif MenuIndex == 2:
                    if MacAddresses[MenuMMIndex] == "none":
                        asyncio.run_coroutine_threadsafe(SetMac(), loop)
                        while Wait:
                            time.sleep(0.01)
                        Wait = True
                    elif MacAddresses[MenuMMIndex] != "none":
                        RemoveMac()
            # FileMenu
            elif MenuDeph >= 2:
                if MenuIndex == 0:
                    FMenuDeph = MenuDeph
                    MenuDeph = 1
                else:
                    FMN()

            if MenuDeph != MenuPrDeph:
                ResetMenu()
            else:
                time.sleep(0.01)
                ButtonEnabled = True
                RotateEnabled = True
        else:
            return
    async def buttonCheck():
        if ButtonEnabled and Wait:
            await asyncio.get_event_loop().run_in_executor(None, pressed)

    asyncio.run_coroutine_threadsafe(buttonCheck(), loop)

def valueChanged(value, direction):
    global MenuPos, CursorPos, MenuMaxPos, MenuIndex, RollingEvent
    MenuPrIndex = MenuIndex
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
        if RollingEvent:
            ResetRolling(MenuPrIndex, CursorPrPos)
        if CursorPos != CursorPrPos:
            Cursor(CursorPrPos)
        if MenuPos != MenuPrPos:
            Menu()
        if MenuDeph <= 1 and len(CurrentSlots[MenuIndex]) >= 16 or MenuDeph >= 2 and len(CurrentSlots[MenuIndex]) >= 19:
            asyncio.run_coroutine_threadsafe(Rolling(), loop)


loop = asyncio.get_event_loop()

if __name__ == "__main__":
    try:
        e1 = Encoder(4, 17, valueChanged)

        GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(buttonPin, GPIO.RISING, callback=buttonPress, bouncetime=300)

        lcd.create_char(0, arrow)
        lcd.create_char(1, back_arrow)
        lcd.create_char(2, no_skript)
        lcd.create_char(3, skript_running)
        lcd.create_char(4, folder_char)

        lcd.clear()
        lcd.cursor_pos = (1, 0)
        lcd.write_string('Welcome to GraviHub!')
        lcd.close()
        ReadMA()
        time.sleep(3)
        lcd.clear()
        Cursor(1)
        Menu()
        time.sleep(1)
        Wait = True
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        lcd.close(clear=True)
        GPIO.cleanup()
        loop.stop()