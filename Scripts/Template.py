from gravitraxconnect import gravitrax_bridge as gb
from gravitraxconnect import gravitrax_constants as gc


# NameCode:
# Start with colour channel script is listening for:
# Red, Green, Blue, Red-Green, Red-Blue, Blue-Green, All
# Next is what the Script does, all Parts are marked with colour:
# r, g, b, rg, rb, bg, a
# First is the stone that the signal was send from:
# Trigger: T, Finish-Trigger: Z, Controller: C, Connect: B, Dome-Stater: D, All: A
# if your script waits for a sequence of signals use "(f)"
# Followed by the stone receiving the signal:
# Dome-Stater: D, Switch: S, Sound: Sm, Lever: L, Connect: B, All: A
# if your script listens to all or is sending to all stones only use the colour
# if the signal is send directly you use "to" if not here are some examples
# (p)= %, (f)= followed by, (t)= times
# Red_rT-70(p)r-30(p)b, Green-Red_rT(f)gT-2(t)rS, All_rT(f)gZ-to-g_rT(f)bZ-to-b
# Scripts using counter can be show using numbers like: Red_rt-2b-3r
# this means red triggers receiving 5 signals send the first two as blue
# and the last 3 as red
# More naming Examples are in the Scripts from YT folder!


async def notification_callback(bridge: gb.Bridge, **signal):  # Code runs when receving a signal
    # your code here
    pass


async def setup(bridge, **kwargs):  # Code runs shortly after connecting
    # your code here
    pass


async def shutdown(bridge, **kwargs):  # Code runs shortly before disconnecting
    # your code here
    pass
