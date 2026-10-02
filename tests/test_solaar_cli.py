"""Exercise the device-selection adapter against Solaar's own matching rules."""
import contextlib
import io
from pathlib import Path
import pkgutil
import runpy
import sys
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/solaar-cli.py'

try:
    # solaar.__version__ is `git describe` of the caller's checkout when run from one.
    INSTALLED_VERSION = pkgutil.get_data('solaar', 'version').strip().decode()
    from solaar.cli import _find_device as installed_find_device
except Exception:
    INSTALLED_VERSION = installed_find_device = None


def reference_find_device(receivers, name):
    """Matching rules of solaar.cli._find_device in Solaar 1.1.20, slot numbers aside."""
    for r in receivers:
        if r.isDevice:
            r.ping()
            r = [r]
        for dev in r:
            if (name == dev.serial.lower() or name == dev.codename.lower()
                    or name == str(dev.kind).lower() or name in dev.name.lower()):
                yield dev


class Receiver:
    isDevice = False
    name = 'Bolt Receiver'

    def __init__(self, *devices):
        self.devices = devices
        for dev in devices:
            dev.receiver = self

    def count(self):
        return len(self.devices)

    def __iter__(self):
        return iter(self.devices)

    def __getitem__(self, number):
        return self.devices[number - 1]


def mouse(serial='', unit='A1B2C3D4', online=True, bluetooth=False, wpid=None, name='MX Master 3S'):
    return types.SimpleNamespace(isDevice=True, name=name, codename=name, kind='mouse', serial=serial,
                                 unitId=unit, wpid=wpid, receiver=None, bluetooth=bluetooth, ping=lambda: online)


class Cases:
    find_device = None

    def cli(self, top_level, *argv):
        """Run the adapter; the stand-in for solaar.cli.run selects like `solaar config`."""
        cli = types.ModuleType('solaar.cli')
        cli._find_device = type(self).find_device

        def run(args):
            dev = next((d for d in cli._find_device(top_level, args[1].lower()) if d.ping()), None)
            if dev is None:
                sys.exit(f"solaar: error: no online device found matching '{args[1].lower()}'")
            print(dev.name, f'({dev.codename}) [{dev.wpid}:{dev.serial}]')
        cli.run = run
        solaar = types.ModuleType('solaar')
        solaar.cli = cli
        output = io.StringIO()
        with patch.dict(sys.modules, {'solaar': solaar, 'solaar.cli': cli}), \
                patch.object(sys, 'argv', ['-c', *argv]), contextlib.redirect_stdout(output):
            try:
                runpy.run_path(str(SCRIPT), run_name='__main__')
                code = 0
            except SystemExit as stop:
                code = stop.code
        return code, output.getvalue().splitlines()

    def test_stock_selection_cannot_address_a_bluetooth_mouse_by_unit_id(self):
        found = type(self).find_device([mouse(bluetooth=True)], 'a1b2c3d4')
        self.assertEqual(list(found), [])

    def test_bluetooth_mouse_is_selected_by_unit_id(self):
        code, lines = self.cli([mouse(bluetooth=True)], 'config', 'A1B2C3D4')
        self.assertEqual((code, lines), (0, ['MX Master 3S (MX Master 3S) [None:]', '# transport: Bluetooth']))

    def test_offline_receiver_pairing_of_the_same_mouse_yields_to_bluetooth(self):
        paired = mouse(serial='A1B2C3D4', online=False, wpid='B034')
        code, lines = self.cli([Receiver(paired), mouse(bluetooth=True)], 'config', 'A1B2C3D4')
        self.assertEqual((code, lines[-1]), (0, '# transport: Bluetooth'))

    def test_receiver_mouse_is_still_selected_by_serial(self):
        paired = mouse(serial='A1B2C3D4', wpid='B034')
        code, lines = self.cli([Receiver(paired)], 'config', 'A1B2C3D4')
        self.assertEqual((code, lines), (0, ['MX Master 3S (MX Master 3S) [B034:A1B2C3D4]', '# transport: Bolt']))

    def test_wired_mouse_is_reported_as_usb(self):
        code, lines = self.cli([mouse()], 'config', 'A1B2C3D4')
        self.assertEqual((code, lines[-1]), (0, '# transport: USB'))

    def test_another_or_sleeping_bluetooth_device_is_never_selected(self):
        for device in (mouse(unit='0FF1CE00', bluetooth=True), mouse(online=False, bluetooth=True)):
            code, lines = self.cli([device], 'config', 'A1B2C3D4')
            self.assertIn('no online device found', str(code))
            self.assertEqual(lines, [])


class ReferenceRules(Cases, unittest.TestCase):
    find_device = staticmethod(reference_find_device)


@unittest.skipUnless(INSTALLED_VERSION == '1.1.20', 'Solaar 1.1.20 is not installed')
class InstalledSolaar(Cases, unittest.TestCase):
    find_device = staticmethod(installed_find_device)


if __name__ == '__main__':
    unittest.main()
