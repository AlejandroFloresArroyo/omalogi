# OMALOGI_SOLAAR_CLI: Solaar's own command line, also selecting a direct device by unit ID.
# Solaar 1.1.20 matches the device argument against serial, codename, kind and name. A mouse
# connected through Bluetooth reports no serial, so its unit ID is the only stable selector.
from itertools import chain
import sys

from solaar import cli

stock = cli._find_device
selected = []


def find_device(receivers, name):
    direct = (d for d in receivers if d.isDevice and str(d.unitId).lower() == name)
    for dev in chain(direct, stock(receivers, name)):
        selected[:] = [dev]
        yield dev


cli._find_device = find_device
cli.run(sys.argv[1:])
if selected:
    dev = selected[0]
    print("# transport:", dev.receiver.name.removesuffix(" Receiver") if dev.receiver
          else "Bluetooth" if dev.bluetooth else "USB")
