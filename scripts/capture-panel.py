"""Capture the native popup by its own read-only geometry, never a tiled client."""
import json
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parents[1] / ".impeccable/review"
root.mkdir(parents=True, exist_ok=True)
subprocess.run(["omarchy-shell", "shell", "summon", "omalogi.mouse"], check=True)
time.sleep(0.5)
monitors = json.loads(subprocess.check_output(["hyprctl", "monitors", "-j"]))
for monitor in monitors:
    target = "omalogi.mouse." + monitor["name"]
    try:
        geometry = json.loads(subprocess.check_output(["omarchy-shell", target, "geometry"], text=True, stderr=subprocess.DEVNULL))
        break
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        continue
else:
    raise RuntimeError("No mapped Omalogi popup exposes geometry")
for page, name in [("Mouse", "mouse"), ("Extras", "extras")]:
    subprocess.run(["omarchy-shell", target, "view", page], check=True)
    deadline = time.monotonic() + 25
    while True:
        geometry = json.loads(subprocess.check_output(["omarchy-shell", target, "geometry"], text=True))
        if not geometry["busy"]:
            break
        if time.monotonic() > deadline:
            raise RuntimeError("The mouse query did not settle")
        time.sleep(0.5)
    time.sleep(0.3)
    x = monitor["x"] + geometry["x"]
    y = monitor["y"] + geometry["y"]
    w = geometry["width"]; h = geometry["height"]
    subprocess.run(["grim", "-g", f"{x},{y} {w}x{h}", str(root / f"{name}.png")], check=True)
    (root / f"{name}.json").write_text(json.dumps(geometry, indent=2))
    print(f"{name}: native popup {w}x{h} at {x},{y}", flush=True)
subprocess.run(["omarchy-shell", target, "view", "Mouse"], check=True)
