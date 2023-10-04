from gravitraxconnect import gravitrax_bridge as gb
from gravitraxconnect import gravitrax_constants as gc

#this script waits for green signals and send each 3 signal as blue
#all other as green.

Count = 0
async def notification_callback(bridge: gb.Bridge, **signal): # Code runs when receving a signal
    global Count
    if signal.get("Header") == gc.MSG_DEFAULT_HEADER:
        status = signal.get("Status")
        color = signal.get("Color")
        stone = signal.get("Stone")
        if color == gc.COLOR_GREEN:
            if Count != 2:
                await bridge.send_signal(status=gc.STATUS_ALL, color_channel=gc.COLOR_GREEN, stone=gc.STONE_BRIDGE,
                                         resends=12)
                Count += 1
            else:
                await bridge.send_signal(status=gc.STATUS_ALL, color_channel=gc.COLOR_BLUE, stone=gc.STONE_BRIDGE,
                                         resends=12)
                Count = 0
async def GBsetup(bridge, bridgeCount=None): # Code runs shortly after connecting
    if bridgeCount == 1:
        await bridge.start_bridge_mode()

async def GBshutdown(bridge, bridgeCount=None): # Code runs shortly before disconnecting
    if bridgeCount == 1:
        await bridge.stop_bridge_mode()