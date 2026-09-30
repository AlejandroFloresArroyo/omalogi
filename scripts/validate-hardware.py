"""Run real CLI checks; physical events and reconnect remain human actions."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path.home() / ".local/bin/omalogi"
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

def cli(*args, config=None):
    p = subprocess.run([str(BINARY), *args], input=json.dumps(config) if config else None,
                       capture_output=True, text=True, timeout=240)
    result = json.loads(p.stdout)
    if p.returncode or not result.get("ok"):
        raise RuntimeError(result.get("error", p.stderr))
    return result

mode = sys.argv[1]
if mode == "prepare":
    status = cli("status")
    if not (ARTIFACTS / "hardware-before.json").exists():
        (ARTIFACTS / "hardware-before.json").write_text(json.dumps(status, indent=2))
    profile = status["config"]
    profile["bindings"] = {event: "diagnostic" for event in profile["bindings"]}
    profile["hardware"].update({"dpi":"1200","hires-smooth-invert":"true",
        "hires-smooth-resolution":"true","scroll-ratchet":"Freespinning",
        "smart-shift":"12","thumb-scroll-invert":"true"})
    result = cli("apply", "--stdin", config=profile)
    (ARTIFACTS / "hardware-apply.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
elif mode == "verify":
    status = cli("status")
    (ARTIFACTS / "hardware-after.json").write_text(json.dumps(status, indent=2))
    expected = set(status["config"]["bindings"])
    seen = {e["event"] for e in status["events"] if e["source"] == "solaar" and e["ok"]}
    print(json.dumps({"ok":True,"physical_events":sorted(seen),"missing":sorted(expected-seen),"dpi":status["devices"][0]["settings"]["dpi"]["value"],"daemon":status["daemon"]}))
elif mode in ("normal", "draft-normal"):
    before = json.loads((ARTIFACTS / "hardware-before.json").read_text())
    profile = before["config"]
    profile["bindings"] = {event:"native" for event in profile["bindings"]}
    profile["bindings"].update({"gesture.click":"apps","gesture.up":"menu","gesture.down":"scratchpad","gesture.left":"workspace.previous","gesture.right":"workspace.next"})
    result = cli("apply" if mode == "normal" else "config", "--stdin", config=profile)
    (ARTIFACTS / ("hardware-normal.json" if mode == "normal" else "hardware-draft.json")).write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
elif mode == "restore":
    print(json.dumps(cli("restore")))
    status = cli("status")
    (ARTIFACTS / "hardware-restored.json").write_text(json.dumps(status, indent=2))
    before = json.loads((ARTIFACTS / "hardware-before.json").read_text())["devices"][0]
    after = status["devices"][0]
    keys = list(status["config"]["hardware"]) + ["hires-scroll-mode","thumb-scroll-mode"]
    for key in keys:
        assert before["settings"][key]["value"] == after["settings"][key]["value"], key
    assert before["buttons"] == after["buttons"]
    print(json.dumps({"ok":True,"restoration_verified":True}))
else:
    raise SystemExit("prepare | verify | normal | draft-normal | restore")
