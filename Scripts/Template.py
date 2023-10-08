from gravitraxconnect import gravitrax_bridge as gb
from gravitraxconnect import gravitrax_constants as gc

#NameCode:
#Start with colour channel script is listening for:
#Red, Green, Blue, Red-Green, Red-Blue, Blue-Green, All
#Next is what the Script does, all Parts are marked with colour:
#r, g, b, rg, rb, bg, a
#First is the stone that the signal was send from:
#Trigger: T, Finish-Trigger: Z, Controller: C, Connect: B, Dome-Stater: D
#if your script waits for an sequence of signals use ">"
#Followed by the stone receiving the signal:
#Dome-Stater: D, Switch: S, Sound: Sm, Lever: L, Connect: B
#if your script listens to all or is sending to all stones only use the colour
#if the signal is send directly you use "to" if not here are some examples
#Red_rT-70%r-30%b, Green-Red_rT>gT-2*rS, All_rT>gZ-to-g_rT>bZ-to-b


async def notification_callback(bridge: gb.Bridge, **signal): #Code runs when receving a signal
    #your code here

async def GBsetup(bridge, bridgeCount=None): #Code runs shortly after connecting
    #your code here

async def GBshutdown(bridge, bridgeCount=None): #Code runs shortly before disconnecting
    #your code here