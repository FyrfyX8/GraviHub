import json

MacAdresses = ["new"]
SlotsMM = ["add new Connection"]

try:
    with open("Connections.json","r") as Connections:
        json_str = json.load(Connections)
        for I in reversed(json_str):
            SlotsMM.insert(0, I)

        for I in SlotsMM:
            if I == "add new Connection":
                pass
            else:
                MacAdresses.insert(0,"none")
        print(SlotsMM)
        print(MacAdresses)
except FileNotFoundError:
    print("Connections.json does not exist creating new one!")
    with open("Connections.json", "x"):
        pass