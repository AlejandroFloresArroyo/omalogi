"""Isolate free-spin persistence across the Solaar service boundary."""
import json
from pathlib import Path
import subprocess
import time
import yaml

ID=json.loads(subprocess.check_output([str(Path.home()/".local/bin/omalogi"),"config"],text=True))["config"]["device_id"]
def read():
    text=subprocess.check_output(["solaar","config",ID,"scroll-ratchet"],text=True)
    live=next(line.split(" = ")[1] for line in text.splitlines() if line.startswith("scroll-ratchet = "))
    devices=yaml.safe_load((Path.home()/".config/solaar/config.yaml").read_text())
    entry=next(d for d in devices if isinstance(d,dict) and d.get("_serial")==ID)
    return {"live":live,"persisted":entry["scroll-ratchet"]}
result={"before":read()}
subprocess.run(["solaar","config",ID,"scroll-ratchet","Freespinning"],check=True,capture_output=True)
time.sleep(.5)
result["after_set"]=read()
subprocess.run(["systemctl","--user","restart","omalogi-solaar.service"],check=True)
time.sleep(1)
result["after_restart"]=read()
(Path(__file__).resolve().parents[1]/"artifacts/probe-scroll.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result))
assert result["after_set"]["live"]=="Freespinning"
assert result["after_restart"]["live"]=="Freespinning", "Solaar startup changed wheel mode"
