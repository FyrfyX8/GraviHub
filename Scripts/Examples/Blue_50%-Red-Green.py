from gravitraxconnect import gravitrax_bridge as gb
from gravitraxconnect import gravitrax_constants as gc
import random
#this script waits for blue signals and sends based on 50& Red or Green signals
async def notification_callback(bridge: gb.Bridge, **signal): # Code runs when receving a signal
    if signal.get("Header") == gc.MSG_DEFAULT_HEADER:
        status = signal.get("Status")
        color = signal.get("Color")
        stone = signal.get("Stone")
        if stone == gc.STONE_FINISH and color == gc.COLOR_BLUE:
            if random.random() < 0.5:
                await bridge.send_signal(status=gc.STATUS_ALL, color_channel=gc.COLOR_RED, stone=gc.STONE_BRIDGE,
                                         resends=12)
            else:
                await bridge.send_signal(status=gc.STATUS_ALL, color_channel=gc.COLOR_GREEN, stone=gc.STONE_BRIDGE,
                                         resends=12)
async def GBsetup(bridge, bridgeCount=None): # Code runs shortly after connecting
    if bridgeCount == 1:
        await bridge.start_bridge_mode()

async def GBshutdown(bridge, bridgeCount=None): # Code runs shortly before disconnecting
    if bridgeCount == 1:
        await bridge.stop_bridge_mode()