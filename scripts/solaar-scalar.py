# LOGI_SCALAR_BRIDGE: one Solaar connection, only the requested scalar settings.
# Solaar 1.1.20's installed HID++ library; capture/GUI remains the external service.
import json
import sys

from logitech_receiver import settings, settings_templates
from solaar.cli import _find_device, _receivers_and_devices

request = json.load(sys.stdin)
allowed = {"dpi", "hires-smooth-invert", "hires-smooth-resolution", "thumb-scroll-invert"}
receivers = []
prepared = {}
before = {}
wrote = False


def text(value):
    return str(value).lower() if isinstance(value, bool) else str(value)


try:
    if not request["values"] or not set(request["values"]) <= allowed:
        raise ValueError("Unsupported scalar change")
    receivers = list(_receivers_and_devices())
    dev = next((d for d in _find_device(receivers, request["id"].lower()) if d.ping()), None)
    if dev is None or request["id"].lower() not in (str(dev.serial).lower(), str(dev.unitId).lower()):
        raise ValueError("The selected mouse is not connected")
    for key, value in request["values"].items():
        setting = settings_templates.check_feature_setting(dev, key)
        if setting is None:
            raise ValueError(f"The mouse does not support {key}")
        if setting.kind == settings.Kind.TOGGLE and value in ("true", "false"):
            desired = value == "true"
        elif setting.kind == settings.Kind.CHOICE and int(value) in setting.choices:
            desired = int(value)
        else:
            raise ValueError(f"Unsupported value for {key}")
        original = setting.read(cached=False)
        if original is None:
            raise ValueError(f"Could not read {key}")
        prepared[key] = (setting, desired)
        before[key] = original
    for key, (setting, value) in prepared.items():
        if before[key] != value:
            wrote = True  # A failed write can have already changed the physical device.
            if setting.write(value, save=False) is None:
                raise ValueError(f"Could not write {key}")
        if setting.read(cached=False) != value:
            raise ValueError(f"The mouse did not confirm {key}")
    print(json.dumps({"ok": True, "before": {k: text(v) for k, v in before.items()}}))
except Exception as error:
    recovered = True
    if wrote:
        for key, original in before.items():
            try:
                setting = prepared[key][0]
                setting.write(original, save=False)
                if setting.read(cached=False) != original:
                    recovered = False
            except Exception:
                recovered = False
    print(json.dumps({"ok": False, "rolled_back": recovered, "error": str(error)}))
finally:
    for receiver in receivers:
        try:
            receiver.close()
        except Exception:
            pass
