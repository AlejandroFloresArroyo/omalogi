import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

HELPER = Path(__file__).resolve().parents[1] / "scripts/solaar-state.py"

class PersistenceTests(unittest.TestCase):
    def test_patch_and_restore_preserve_foreign_device_keys_and_numeric_buttons(self):
        original = ["1.1.20", {"_serial":"A1B2C3D4", "dpi":1000, "divert-keys":{83:2, 196:0}, "unrelated":"keep"}, {"_serial":"OTHER", "dpi":500}]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"config.yaml"
            path.write_text(yaml.safe_dump(original))
            def call(op, **extra):
                request={"op":op,"id":"A1B2C3D4","path":str(path),"keys":["dpi","hires-smooth-invert"],"buttons":["83"],**extra}
                return json.loads(subprocess.check_output(["python3",str(HELPER)],input=json.dumps(request).encode()))
            baseline=call("read")
            call("sensitive")
            changed=yaml.safe_load(path.read_text())
            self.assertEqual(changed[1]["_sensitive"]["hires-smooth-invert"], True)
            changed[1]["dpi"]=1600
            changed[1]["hires-smooth-invert"]=True
            changed[1]["divert-keys"][83]=1
            changed[1]["divert-keys"][196]=1
            path.write_text(yaml.safe_dump(changed))
            call("restore",original=baseline)
            restored=yaml.safe_load(path.read_text())
            self.assertEqual(restored[1]["dpi"],1000)
            self.assertNotIn("hires-smooth-invert",restored[1])
            self.assertNotIn("_sensitive",restored[1])
            self.assertEqual(restored[1]["divert-keys"],{83:2,196:1})
            self.assertEqual(restored[1]["unrelated"],"keep")
            self.assertEqual(restored[2],original[2])

if __name__ == "__main__": unittest.main()
