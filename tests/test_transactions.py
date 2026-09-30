"""Exercise the compiled CLI against process boundaries and injected failure."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "target/debug/omalogi"
FAKE = '''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
import yaml
p=Path(os.environ["XDG_CONFIG_HOME"])/"solaar/config.yaml"
d=yaml.safe_load(p.read_text()); x=d[1]
args=sys.argv[1:]
with (p.parent/"calls.jsonl").open("a") as log: log.write(json.dumps(args)+"\\n")
if args[0]=="show":
 print("Bolt Receiver\\n  1: MX Master 3S\\n     Serial number: A1B2C3D4"); sys.exit(0)
transient=p.parent/"fail-read-once"
if len(args)==2 and transient.exists(): transient.unlink(); sys.exit(1)
key=args[2] if len(args)>2 else None
buttons={83:"Back Button",86:"Forward Button",195:"Mouse Gesture Button"}
if len(args)>3:
 value=args[-1]
 if key=="dpi" and value=="1600" and os.environ.get("FAIL_DPI")=="1":
  x[key]=1600; p.write_text(yaml.safe_dump(d)); sys.exit(1)
 if key=="divert-keys":
  n=next(n for n,label in buttons.items() if label==args[3])
  x[key][n]={"Regular":0,"Diverted":1,"Mouse Gestures":2,"Sliding DPI":3}[value]
 elif key=="scroll-ratchet": x[key]={"Ratcheted":2,"Freespinning":1}[value]
 else: x[key]=value.lower()=="true" if value.lower() in ("true","false") else int(value)
 p.write_text(yaml.safe_dump(d))
print("MX Master 3S (MX Master 3S) [B034:A1B2C3D4]")
for k in ["dpi","scroll-ratchet","smart-shift","hires-smooth-invert","hires-smooth-resolution","hires-scroll-mode","thumb-scroll-invert","thumb-scroll-mode"]:
 if key and k!=key: continue
 v=1 if k=="smart-shift" and x["scroll-ratchet"]==1 else x[k]
 if k=="dpi": print("#   possible values: one of [ 400, 1000, 1600, 8000 ]")
 if k=="scroll-ratchet": print("#   possible values: one of [ Freespinning, Ratcheted ]"); v={1:"Freespinning",2:"Ratcheted"}[v]
 if isinstance(v,bool): print("#   possible values: on/true/t or off/false")
 print(f"{k} = {v}")
if not key or key=="divert-keys":
 print("divert-keys = {"+", ".join(f"{label}:{'Regular' if x['divert-keys'][n]==0 else 'Diverted'}" for n,label in buttons.items())+"}")
'''

FAKE_BRIDGE = '''#!/usr/bin/python3
import json,os,subprocess,sys
from pathlib import Path
if len(sys.argv)>2 and sys.argv[2].startswith("# LOGI_SCALAR_BRIDGE"):
 req=json.load(sys.stdin)
 p=Path(os.environ["XDG_CONFIG_HOME"])/"solaar/config.yaml"
 import yaml
 before=yaml.safe_load(p.read_text())[1]
 old={k:before[k] for k in req["values"]}
 try:
  for k,v in req["values"].items():
   r=subprocess.run(["solaar","config",req["id"],k,str(v)],capture_output=True)
   if os.environ.get("CRASH_FAST_BRIDGE")=="1": sys.exit(1)
   if r.returncode: raise ValueError("injected write failure")
  print(json.dumps({"ok":True,"before":{k:str(v).lower() if isinstance(v,bool) else str(v) for k,v in old.items()}}))
 except Exception as e:
  for k,v in old.items(): subprocess.run(["solaar","config",req["id"],k,str(v)],capture_output=True)
  print(json.dumps({"ok":False,"rolled_back":True,"error":str(e)}))
else:
 os.execv("/usr/bin/python3",["python3",*sys.argv[1:]])
'''

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "solaar/config.yaml"
        self.config.parent.mkdir()
        self.original = ["1.1.20", {"_serial":"A1B2C3D4","dpi":1000,"scroll-ratchet":2,"smart-shift":10,
            "hires-smooth-invert":False,"hires-smooth-resolution":False,"hires-scroll-mode":False,
            "thumb-scroll-invert":False,"thumb-scroll-mode":False,"divert-keys":{83:0,86:0,195:2},"foreign":42}]
        self.config.write_text(yaml.safe_dump(self.original))
        self.foreign = "# preserve exact whitespace\n---\n- Device: OTHER\n- Execute: [/usr/bin/true]\n..."
        (self.config.parent / "rules.yaml").write_text(self.foreign)
        fake = self.root / "bin"; fake.mkdir()
        for name,text in {"solaar":FAKE,"systemctl":"#!/bin/sh\nexit 0\n","pgrep":"#!/bin/sh\nexit 1\n"}.items():
            p=fake/name; p.write_text(text); p.chmod(0o755)
        # Keep the production scalar adapter's process seam isolated from real HID devices.
        bridge = fake/"python3"
        bridge.write_text(FAKE_BRIDGE)
        bridge.chmod(0o755)
        self.env={**os.environ,"XDG_CONFIG_HOME":str(self.root),"PATH":str(fake)+":/usr/bin"}
    def tearDown(self): self.temp.cleanup()
    def cli(self,*args,input=None, fail=False):
        p=subprocess.run([str(BINARY),*args],input=json.dumps(input) if input else None,
            text=True,capture_output=True,env={**self.env,"FAIL_DPI":"1" if fail else "0"},timeout=20)
        return p.returncode,json.loads(p.stdout)
    def test_apply_restore_preserves_foreign_rules_and_software_gesture_mode(self):
        _,status=self.cli("status"); c=status["config"]
        c["hardware"]["dpi"]="1600"
        rc,result=self.cli("apply","--stdin",input=c)
        self.assertEqual((rc,result["ok"]),(0,True))
        self.assertEqual(yaml.safe_load(self.config.read_text())[1]["dpi"],1600)
        self.assertTrue((self.config.parent/"rules.yaml").read_text().endswith(self.foreign))
        rc,result=self.cli("restore")
        self.assertEqual((rc,result["ok"]),(0,True))
        restored=yaml.safe_load(self.config.read_text())
        self.assertEqual(restored,self.original)
        self.assertEqual((self.config.parent/"rules.yaml").read_text(),self.foreign)
    def test_failed_write_rolls_back_even_if_backend_persisted_attempted_value(self):
        _,status=self.cli("status"); c=status["config"]; c["hardware"]["dpi"]="1600"
        rc,result=self.cli("apply","--stdin",input=c,fail=True)
        self.assertEqual((rc,result["ok"]),(1,False))
        self.assertIn("Previous settings were restored",result["error"])
        self.assertEqual(yaml.safe_load(self.config.read_text()),self.original)
        self.assertEqual((self.config.parent/"rules.yaml").read_text(),self.foreign)
        self.assertFalse((self.root/"omalogi/state.json").exists())
    def test_second_apply_restores_first_install_baseline(self):
        _,status=self.cli("status"); c=status["config"]
        c["hardware"]["dpi"]="1600"; self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        c["hardware"]["dpi"]="8000"; self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        self.assertEqual(self.cli("restore")[0],0)
        self.assertEqual(yaml.safe_load(self.config.read_text()),self.original)

    def test_freespin_keeps_saved_threshold_while_physical_read_is_one(self):
        _,status=self.cli("status"); c=status["config"]
        c["hardware"]["smart-shift"]="12"
        c["hardware"]["scroll-ratchet"]="Freespinning"
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        _,status=self.cli("status")
        self.assertEqual(status["devices"][0]["settings"]["smart-shift"]["value"],"1")
        self.assertEqual(status["config"]["hardware"]["smart-shift"],"12")
        self.assertEqual(yaml.safe_load(self.config.read_text())[1]["smart-shift"],12)
        self.assertEqual(self.cli("restore")[0],0)
        self.assertEqual(yaml.safe_load(self.config.read_text()),self.original)

    def test_startup_read_failure_is_retried_without_modifying_mouse(self):
        (self.config.parent/"fail-read-once").touch()
        rc,status=self.cli("status")
        self.assertEqual((rc,status["ok"]),(0,True))
        self.assertEqual(status["devices"][0]["id"],"A1B2C3D4")
        self.assertEqual(yaml.safe_load(self.config.read_text()),self.original)


    def writes(self):
        calls=self.config.parent/"calls.jsonl"
        return [json.loads(line) for line in calls.read_text().splitlines() if len(json.loads(line))>3]

    def test_incremental_dpi_apply_does_not_rewrite_other_controls(self):
        _,status=self.cli("status"); c=status["config"]
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        (self.config.parent/"calls.jsonl").write_text("")
        c["hardware"]["dpi"]="1600"
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        self.assertEqual([a[2] for a in self.writes()],["dpi"])
        self.assertEqual(self.cli("restore")[0],0)
        self.assertEqual(yaml.safe_load(self.config.read_text()),self.original)

    def test_binding_change_only_writes_that_button(self):
        _,status=self.cli("status"); c=status["config"]
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        (self.config.parent/"calls.jsonl").write_text("")
        c["bindings"]["button.forward"]="volume.up"
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        self.assertEqual([a[2:] for a in self.writes()],[["divert-keys","Forward Button","Diverted"]])

    def test_free_spin_dpi_change_preserves_stored_smartshift_without_rewriting_it(self):
        _,status=self.cli("status"); c=status["config"]
        c["hardware"]["scroll-ratchet"]="Freespinning"
        c["hardware"]["smart-shift"]="12"
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        (self.config.parent/"calls.jsonl").write_text("")
        c["hardware"]["dpi"]="1600"
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        self.assertEqual([a[2] for a in self.writes()],["dpi"])
        self.assertEqual(yaml.safe_load(self.config.read_text())[1]["smart-shift"],12)


    def test_dpi_fast_update_does_not_scan_all_settings(self):
        _,status=self.cli("status"); c=status["config"]
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        (self.config.parent/"calls.jsonl").write_text("")
        c["hardware"]["dpi"]="1600"
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        calls=[json.loads(line) for line in (self.config.parent/"calls.jsonl").read_text().splitlines()]
        self.assertFalse(any(a==["config",c["device_id"]] for a in calls),calls)

    def test_action_only_update_performs_no_hid_operations(self):
        _,status=self.cli("status"); c=status["config"]
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        (self.config.parent/"calls.jsonl").write_text("")
        c["bindings"]["gesture.click"]="audio"
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        self.assertEqual((self.config.parent/"calls.jsonl").read_text(),"")

    def test_failed_fast_update_restores_previous_applied_profile(self):
        _,status=self.cli("status"); c=status["config"]
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        c["hardware"]["dpi"]="1600"
        rc,result=self.cli("apply","--stdin",input=c,fail=True)
        self.assertEqual((rc,result["ok"]),(1,False))
        self.assertEqual(yaml.safe_load(self.config.read_text())[1]["dpi"],1000)
        state=json.loads((self.root/"omalogi/state.json").read_text())
        self.assertTrue(state["applied"]); self.assertFalse(state["pending"])
        self.assertEqual(state["config"]["hardware"]["dpi"],"1000")


    def test_interrupted_fast_update_requires_restore_and_preserves_original_baseline(self):
        _,status=self.cli("status"); c=status["config"]
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],0)
        c["hardware"]["dpi"]="1600"
        self.env["CRASH_FAST_BRIDGE"]="1"
        rc,result=self.cli("apply","--stdin",input=c)
        self.env.pop("CRASH_FAST_BRIDGE")
        self.assertEqual((rc,result["ok"]),(1,False))
        self.assertIn("Run Restore",result["error"])
        state=json.loads((self.root/"omalogi/state.json").read_text())
        self.assertTrue(state["pending"]); self.assertFalse(state["applied"])
        self.assertEqual(self.cli("apply","--stdin",input=c)[0],1)
        self.assertEqual(self.cli("restore")[0],0)
        self.assertEqual(yaml.safe_load(self.config.read_text()),self.original)
        self.assertEqual((self.config.parent/"rules.yaml").read_text(),self.foreign)

if __name__=="__main__": unittest.main()
