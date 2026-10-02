"""Exercise the real adapter's readback/rollback against a simulated HID setting."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/solaar-scalar.py'

class ScalarBridgeTests(unittest.TestCase):
    def bridge(self, desired='1600', fail=False, rollback_fail=False, serial='A1B2C3D4', stale=False, direct=False):
        class Setting:
            kind = 'choice'
            choices = [1000, 1600, 8000]
            value = 1000
            writes = []
            def read(self, cached=True):
                assert cached is False
                return 1000 if stale else self.value
            def write(self, value, save=True):
                assert save is False
                self.writes.append(value)
                if rollback_fail and value == 1000:
                    return None
                self.value = value
                return None if fail and value == 1600 else value
        setting = Setting()
        # A Bluetooth mouse is itself a top-level entry and reports no serial, only a unit ID.
        dev = types.SimpleNamespace(serial='' if direct else serial, unitId=serial, isDevice=True,
                                    ping=lambda: True, close=lambda: None)
        receiver = types.SimpleNamespace(isDevice=False, close=lambda: None)
        mods = {
            'logitech_receiver': types.ModuleType('logitech_receiver'),
            'logitech_receiver.settings': types.ModuleType('logitech_receiver.settings'),
            'logitech_receiver.settings_templates': types.ModuleType('logitech_receiver.settings_templates'),
            'solaar': types.ModuleType('solaar'),
            'solaar.cli': types.ModuleType('solaar.cli'),
        }
        mods['logitech_receiver.settings'].Kind = types.SimpleNamespace(CHOICE='choice', TOGGLE='toggle')
        mods['logitech_receiver.settings_templates'].check_feature_setting = lambda d,k: setting
        mods['solaar.cli']._find_device = lambda receivers,ident: [] if direct else [dev]
        mods['solaar.cli']._receivers_and_devices = lambda: [dev] if direct else [receiver]
        output = io.StringIO()
        with patch.dict(sys.modules, mods), patch('sys.stdin', io.StringIO(json.dumps({'id':'A1B2C3D4','values':{'dpi':desired}}))), contextlib.redirect_stdout(output):
            runpy.run_path(str(SCRIPT),run_name='__main__')
        return json.loads(output.getvalue()),setting

    def test_success_requires_fresh_physical_readback_and_never_saves_via_solaar(self):
        result,s=self.bridge()
        self.assertTrue(result['ok']); self.assertEqual(result['before'],{'dpi':'1000'})
        self.assertEqual((s.value,s.writes),(1600,[1600]))

    def test_failed_write_can_have_changed_hardware_and_must_be_rolled_back(self):
        result,s=self.bridge(fail=True)
        self.assertFalse(result['ok']); self.assertTrue(result['rolled_back'])
        self.assertEqual((s.value,s.writes),(1000,[1600,1000]))

    def test_failed_rollback_is_not_reported_as_recovered(self):
        result,s=self.bridge(fail=True,rollback_fail=True)
        self.assertFalse(result['ok']); self.assertFalse(result['rolled_back'])
        self.assertEqual(s.value,1600)

    def test_invalid_value_is_rejected_before_any_write(self):
        result,s=self.bridge(desired='1601')
        self.assertFalse(result['ok']); self.assertEqual(s.writes,[])

    def test_wrong_device_identity_is_rejected_before_any_write(self):
        result,s=self.bridge(serial='OTHER')
        self.assertFalse(result['ok']); self.assertEqual(s.writes,[])

    def test_write_ack_is_not_enough_when_physical_readback_disagrees(self):
        result,s=self.bridge(stale=True)
        self.assertFalse(result['ok']); self.assertTrue(result['rolled_back'])
        self.assertEqual(s.writes,[1600,1000])

    def test_bluetooth_mouse_without_serial_is_selected_by_unit_id(self):
        result,s=self.bridge(direct=True)
        self.assertTrue(result['ok']); self.assertEqual(result['before'],{'dpi':'1000'})
        self.assertEqual((s.value,s.writes),(1600,[1600]))

    def test_another_bluetooth_device_is_rejected_before_any_write(self):
        result,s=self.bridge(serial='OTHER',direct=True)
        self.assertFalse(result['ok']); self.assertEqual(s.writes,[])
