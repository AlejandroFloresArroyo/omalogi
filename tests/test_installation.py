"""Installation, native-checkout ownership and migration in an isolated HOME."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_files', ROOT / 'scripts/install-files.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='omalogi-install-test-')
        self.home = Path(self.temp.name) / 'home'
        self.home.mkdir()
        self.config = self.home / '.config'
        self.env = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.config)})
        self.env.start()
        self.services = patch.object(module.subprocess, 'run')
        self.services.start()
        self.project = Path(self.temp.name) / 'source'
        (self.project / 'plugin').mkdir(parents=True)
        (self.project / 'manifest.json').write_bytes((ROOT / 'manifest.json').read_bytes())
        for n in module.QML:
            (self.project / 'plugin' / n).write_bytes((ROOT / 'plugin' / n).read_bytes())
        self.binary = self.project / 'omalogi'
        self.binary.write_text('#!/bin/sh\necho omalogi 0.1.0-beta.1\n')
        self.binary.chmod(0o755)
        shell = self.config / 'omarchy/shell.json'
        shell.parent.mkdir(parents=True)
        shell.write_text(json.dumps({'bar': {'layout': {'right': [{'id': 'omarchy.audio'}, {'id': 'local.logi', 'custom': 42}]}},
                                    'plugins': [{'id': 'foreign.plugin'}], 'idle': {'lock': 7200}}))
        self.install = module.Installation(self.project, self.binary)

    def tearDown(self):
        self.services.stop()
        self.env.stop()
        self.temp.cleanup()

    def legacy(self):
        app = self.config / 'omarchy-logi'
        app.mkdir()
        for path in self.install.legacy_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('legacy-owned-content')
        (app / 'install.json').write_text(json.dumps({'version': 1, 'files': sorted(str(p) for p in self.install.legacy_paths)}))
        profile = {'version': 1, 'device_id': 'TEST1234', 'hardware': {'dpi': '1350'}, 'bindings': {'gesture.click': 'apps'}}
        (app / 'profile.json').write_text(json.dumps(profile))
        (app / 'state.json').write_text(json.dumps({'applied': True, 'pending': False, 'baseline': {'persisted': {'dpi': 1000}}, 'config': profile}))
        (app / 'events.json').write_text('[{"source":"solaar"}]')
        solaar = self.config / 'solaar'
        solaar.mkdir()
        (solaar / 'config.yaml').write_text('foreign-device: untouched\n')
        block = '# BEGIN OMARCHY-LOGI v1\n---\n- Execute: [' + json.dumps(str(self.home / '.local/bin/omarchy-logi')) + ', trigger, gesture.click]\n...\n# END OMARCHY-LOGI v1\n'
        self.foreign = '# exact foreign whitespace\n---\n- Execute: [/usr/bin/true]\n...'
        (solaar / 'rules.yaml').write_text(block + self.foreign)
        return app

    def test_install_reinstall_and_remove_only_owned_files(self):
        original = (self.config / 'omarchy/shell.json').read_bytes()
        self.install.install()
        self.install.install()
        self.assertEqual((self.home / '.local/bin/omalogi').stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.config / 'omarchy/shell.json').read_bytes(), original)
        self.assertEqual((self.install.plugin / 'manifest.json').read_bytes(), (self.project / 'manifest.json').read_bytes())
        foreign = self.install.plugin / 'personal.txt'
        foreign.write_text('keep')
        self.install.uninstall()
        self.assertEqual(foreign.read_text(), 'keep')
        self.assertTrue((self.install.app / 'shell-before-install.json').exists())
        self.assertFalse((self.home / '.local/bin/omalogi').exists())

    def test_foreign_file_collision_has_no_partial_writes(self):
        self.install.service.parent.mkdir(parents=True)
        self.install.service.write_text('foreign')
        with self.assertRaisesRegex(ValueError, 'ajeno'):
            self.install.install()
        self.assertFalse((self.home / '.local/bin/omalogi').exists())
        self.assertEqual(self.install.service.read_text(), 'foreign')

    def test_native_checkout_keeps_git_and_qml_unmodified(self):
        native = self.install.plugin
        native.mkdir(parents=True)
        (native / '.git').mkdir()
        for p in self.project.rglob('*'):
            target = native / p.relative_to(self.project)
            if p.is_dir(): target.mkdir(exist_ok=True)
            else: target.write_bytes(p.read_bytes())
        native_install = module.Installation(native, self.binary)
        before = (native / 'plugin/OmalogiWidget.qml').read_bytes()
        native_install.install()
        native_install.install()
        receipt = json.loads((native_install.app / 'install.json').read_text())
        self.assertEqual(receipt['pluginMode'], 'git')
        self.assertFalse(any(str(native) in name for name in receipt['files']))
        native_install.uninstall()
        self.assertTrue((native / '.git').exists())
        self.assertEqual((native / 'plugin/OmalogiWidget.qml').read_bytes(), before)

    def test_source_install_refuses_to_overwrite_native_git_checkout(self):
        (self.install.plugin / '.git').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'checkout'):
            self.install.install()

    def test_migration_preserves_profile_snapshot_foreign_rules_and_placement(self):
        legacy = self.legacy()
        profile = (legacy / 'profile.json').read_bytes()
        state = (legacy / 'state.json').read_bytes()
        self.install.install()
        self.assertFalse(legacy.exists())
        self.assertEqual((self.install.app / 'profile.json').read_bytes(), profile)
        self.assertEqual((self.install.app / 'state.json').read_bytes(), state)
        self.assertEqual((self.config / 'solaar/config.yaml').read_text(), 'foreign-device: untouched\n')
        rules = (self.config / 'solaar/rules.yaml').read_text()
        self.assertTrue(rules.startswith('# BEGIN OMALOGI v1\n'))
        self.assertIn(json.dumps(str(self.home / '.local/bin/omalogi')), rules)
        self.assertTrue(rules.endswith(self.foreign))
        shell = json.loads((self.config / 'omarchy/shell.json').read_text())
        self.assertEqual(shell['bar']['layout']['right'][1], {'id': 'omalogi.mouse', 'custom': 42})
        self.assertEqual(shell['plugins'], [{'id': 'foreign.plugin'}])
        self.assertEqual(shell['idle']['lock'], 7200)
        self.assertTrue((self.install.app / 'legacy-install.json').exists())
        self.assertTrue(all(not p.exists() for p in self.install.legacy_paths))
        self.install.install()  # Retrying migration completion is safe.

    def test_pending_transaction_stops_migration(self):
        legacy = self.legacy()
        (legacy / 'state.json').write_text('{"pending":true}')
        with self.assertRaisesRegex(ValueError, 'pendiente'):
            self.install.install()
        self.assertTrue(legacy.exists())
        self.assertFalse(self.install.app.exists())

    def test_migration_refuses_two_configuration_directories(self):
        self.legacy()
        self.install.app.mkdir()
        with self.assertRaisesRegex(ValueError, 'dos directorios'):
            self.install.install()

    def test_failed_migration_rolls_back_files_and_directory_move(self):
        legacy = self.legacy()
        rules = (self.config / 'solaar/rules.yaml').read_bytes()
        receipt = (legacy / 'install.json').read_bytes()
        real_atomic = module.atomic
        failed = False
        def fail_once(path, content, mode=0o644):
            nonlocal failed
            if path == self.install.service and not failed:
                failed = True
                raise OSError('injected service write failure')
            real_atomic(path, content, mode)
        with patch.object(module, 'atomic', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.install.install()
        self.assertTrue(legacy.exists())
        self.assertFalse(self.install.app.exists())
        self.assertEqual((legacy / 'install.json').read_bytes(), receipt)
        self.assertEqual((self.config / 'solaar/rules.yaml').read_bytes(), rules)
        self.assertTrue(all(p.exists() for p in self.install.legacy_paths))
        self.assertFalse((self.home / '.local/bin/omalogi').exists())

    def test_unknown_uninstall_receipt_path_cannot_delete_foreign_data(self):
        self.install.install()
        foreign = self.home / 'precious.txt'
        foreign.write_text('keep')
        (self.install.app / 'install.json').write_text(json.dumps({'files': [str(foreign)]}))
        with self.assertRaisesRegex(ValueError, 'desconocidas'):
            self.install.uninstall()
        self.assertEqual(foreign.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
