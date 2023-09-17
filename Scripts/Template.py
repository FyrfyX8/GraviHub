import asyncio
from gravitraxconnect import gravitrax_bridge as gb
from gravitraxconnect import gravitrax_constants as gc
bridge = gb.Bridge()

async def notification_callback(bridge: gb.Bridge, **signal):
    if signal.get("Header") == gc.MSG_DEFAULT_HEADER:
        status = signal.get("Status")
        stone = signal.get('Stone')
        color = signal.get('Color')
        await bridge.send_signal(gc.STATUS_ALL, color, stone=gc.STONE_BRIDGE)

async def setup():
    print("Setup")
    if await bridge.send_signal(status=gc.STATUS_LOCK, color_channel=gc.COLOR_BLUE, resends=15):
        pass