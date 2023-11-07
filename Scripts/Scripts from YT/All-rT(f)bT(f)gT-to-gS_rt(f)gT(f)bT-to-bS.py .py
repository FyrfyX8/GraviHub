from gravitraxconnect import gravitrax_bridge as gb
from gravitraxconnect import gravitrax_constants as gc
#this script waits for the sequence red blue green or red green blue
#from triggers, to determine to send Blue/Green signal.

sequence = []

async def notification_callback(bridge: gb.Bridge, **signal): # Code runs when receving a signal
    global sequence
    if signal.get("Header") == gc.MSG_DEFAULT_HEADER:
        status = signal.get("Status")
        color = signal.get("Color")
        stone = signal.get("Stone")
        if stone == gc.STONE_TRIGGER and color == gc.COLOR_RED and len(sequence) == 0:
            sequence.append("red")
        elif stone == gc.STONE_TRIGGER and len(sequence) == 1:
            if color == gc.COLOR_GREEN:
                sequence.append("green")
            elif color == gc.COLOR_BLUE:
                sequence.append("blue")
            else:
                sequence = []
        elif stone == gc.STONE_TRIGGER and len(sequence) == 2:
            if ((color == gc.COLOR_GREEN and sequence[1] == "blue") or
                    (color == gc.COLOR_BLUE and sequence[1] == "green")):
                await bridge.send_signal(status=gc.STATUS_SWITCH, color_channel=color, stone=gc.STONE_BRIDGE,
                                         resends=12)
            sequence = []


async def setup(bridge, bridgeCount=None): # Code runs shortly after connecting
    if bridgeCount == 1:
        await bridge.start_bridge_mode()

async def shutdown(bridge, **kwargs):  # Code runs shortly before disconnecting
    if kwargs.get("bridge_count") == 1:
        await bridge.stop_bridge_mode()