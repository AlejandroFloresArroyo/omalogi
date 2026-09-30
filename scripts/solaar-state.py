"""Selective Solaar persistence adapter; never imports Solaar implementation."""
import json
import os
from pathlib import Path
import sys
import tempfile
import yaml

request = json.load(sys.stdin)
path = Path(request["path"])
data = yaml.safe_load(path.read_text()) if path.exists() else ["1.1.20"]
if not isinstance(data, list):
    raise ValueError("Solaar config.yaml is not a sequence")
entry = next((d for d in data if isinstance(d, dict) and request["id"] in
              (d.get("_serial"), d.get("_unitId"))), None)
if entry is None:
    raise ValueError("Selected device is absent from Solaar persistence")
if request["op"] == "read":
    print(json.dumps(entry))
    sys.exit(0)

keys = request["keys"]
buttons = request["buttons"]
if request["op"] == "sensitive":
    entry.setdefault("_sensitive", {}).update({k: True for k in keys})
elif request["op"] == "values":
    # The scalar bridge never saves through Solaar; persist only our changed keys.
    for key in keys:
        entry[key] = request["original"][key]
    entry.setdefault("_sensitive", {}).update({k: True for k in keys})
elif request["op"] == "restore":
    original = request["original"]
    for key in keys:
        if key in original:
            entry[key] = original[key]
        else:
            entry.pop(key, None)
    for key in ("divert-keys", "_sensitive"):
        subset = buttons if key == "divert-keys" else keys
        target = entry.setdefault(key, {})
        old = original.get(key, {})
        for k in subset:
            actual = int(k) if key == "divert-keys" else k
            if str(k) in old:
                target[actual] = old[str(k)]
            else:
                target.pop(actual, None)
        if not target and key not in original:
            entry.pop(key, None)
else:
    raise ValueError("Unknown operation")
path.parent.mkdir(parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix=".omalogi-", dir=path.parent)
try:
    with os.fdopen(fd, "w") as out:
        yaml.safe_dump(data, out, sort_keys=False)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
print("{}")
