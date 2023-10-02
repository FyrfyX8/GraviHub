import asyncio
from gravitraxconnect import gravitrax_bridge as gb
from gravitraxconnect import gravitrax_constants as gc


async def notification_callback(bridge: gb.Bridge, **signal): # Code runs when receving a signal
    # your code here

async def GBsetup(bridge, bridgeCount=None): # Code runs shortly after connecting
    # your code here

async def GBshutdown(bridge, bridgeCount=None): # Code runs shortly before disconnecting
    # your code here