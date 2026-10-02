"""Run the actual QML widget in an isolated shell against a slow, fake CLI.

No HID writes or installation. Native qs.Ui supplies the same popup lifecycle.
"""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FAKE = '''#!/usr/bin/python3
import json,sys,time
from pathlib import Path
root=Path(__file__).parent
c=json.loads((root/'profile.json').read_text())
op=sys.argv[1]
if op=='status':
 d={'id':c['device_id'],'name':c['device_name'],'transport':'Bluetooth','settings':{k:{'value':v,'choices':[str(n) for n in range(200,8001,50)] if k=='dpi' else ['Ratcheted','Freespinning'],'toggle':v in ['true','false']} for k,v in c['hardware'].items()}}
 print(json.dumps({'ok':True,'devices':[d],'config':c,'actions':[],'events':[],'applied':True,'pending':False,'daemon':True}))
elif op=='apply':
 c=json.loads(sys.stdin.read())
 with (root/'calls.jsonl').open('a') as log: log.write(json.dumps(c)+'\\n')
 time.sleep(.65)
 if c['hardware']['dpi']=='1050' and not (root/'failed-once').exists():
  (root/'failed-once').touch();print(json.dumps({'ok':False,'error':'Simulated write failure, rollback complete'}));sys.exit(1)
 (root/'profile.json').write_text(json.dumps(c))
 print(json.dumps({'ok':True,'config':c,'message':'Simulated verified'}))
else: print('{"ok":true,"events":[]}')
'''
QML = '''import QtQuick
import Quickshell
import "plugin"
ShellRoot {
    id: test
    property int stage: 0
    property var panel: null
    property int errorWait: 0
    function check(ok, message) {
        if (!ok) { console.log("REGRESSION_RESULT " + JSON.stringify({ok:false,error:message})); Qt.quit(); throw new Error(message) }
    }
    QtObject {
        id: bar
        property string position: "top"
        property int barSize: 26
        property bool vertical: false
        property string fontFamily: "monospace"
        property color barForeground: "white"
        property color urgent: "red"
        property color foreground: "white"
        property color background: "black"
        property bool foregroundAnimationEnabled: false
        property var activePopout: null
        function requestPopout(p) { activePopout = p }
        function releasePopout(p) { activePopout = null }
        function hideTooltip(p) {}
        function showTooltip(p,t) {}
    }
    PanelWindow {
        screen: Quickshell.screens[0]; visible: false
        anchors { top: true; left: true; right: true }
        implicitHeight: 26
        OmalogiWidget { id: widget; bar: bar }
    }
    Timer {
        interval: 80; repeat: true; running: true
        onTriggered: {
            var p = test.panel
            if (test.stage === 0) {
                test.panel = widget.children[1]; widget.open(); test.stage = 1
            } else if (test.stage === 1 && !p.busy && p.profile) {
                test.check(p.connection === "Bluetooth · TEST1234 · Connected", "header names the live transport")
                p.patch("hardware","dpi","1600")
                p.patch("hardware","dpi","2400")
                p.patch("hardware","dpi","3200")
                test.stage = 2
            } else if (test.stage === 2 && p.mutating) {
                test.check(p.hardware("dpi") === "3200", "debounced last value")
                p.patch("hardware","dpi","1000")
                test.check(p.hardware("dpi") === "1000", "editing while apply remains enabled")
                widget.close()
                test.check(!widget.opened && p.mutating, "busy outside-close must release popup and keep process alive")
                widget.open()
                test.check(p.hardware("dpi") === "1000", "reopen preserves queued value")
                widget.close(); test.stage = 3
            } else if (test.stage === 3 && !p.busy && !p.dirty) {
                test.check(p.hardware("dpi") === "1000", "old result must not replace queued value")
                p.patch("hardware","dpi","1050"); test.stage = 4
            } else if (test.stage === 4 && p.failed && !p.busy) {
                test.check(p.dirty && p.hardware("dpi") === "1050", "failure keeps desired value")
                test.errorWait++; if (test.errorWait > 12) {
                    p.command("apply"); test.stage = 5
                }
            } else if (test.stage === 5 && !p.busy && !p.dirty && !p.failed) {
                console.log("REGRESSION_RESULT " + JSON.stringify({ok:true,closed:!widget.opened,finalDpi:p.hardware("dpi")}))
                running = false; Qt.quit()
            }
        }
    }
}
'''

with tempfile.TemporaryDirectory(prefix="omalogi-panel-test-") as temp:
    base = Path(temp)
    for name in ["Ui", "Commons"]:
        (base / name).symlink_to(Path("/usr/share/omarchy/shell") / name, target_is_directory=True)
    (base / "plugin").mkdir()
    for src in (ROOT / "plugin").glob("*.qml"):
        text = src.read_text()
        if src.name == "OmalogiPanel.qml":
            text = text.replace('Quickshell.env("HOME") + "/.local/bin/omalogi"', json.dumps(str(base / "fake-cli")))
        (base / "plugin" / src.name).write_text(text)
    (base / "fake-cli").write_text(FAKE)
    (base / "fake-cli").chmod(0o755)
    profile = {
        "version": 1, "device_id": "TEST1234", "device_name": "MX Master 3S",
        "hardware": {"dpi": "1000", "scroll-ratchet": "Ratcheted", "smart-shift": "10"},
        "bindings": {event: "native" for event in [
            "gesture.click", "gesture.up", "gesture.down", "gesture.left", "gesture.right",
            "button.back", "button.forward", "wheel.up", "wheel.down", "thumb.left", "thumb.right"
        ]}, "wheel_interval_ms": 120,
    }
    (base / "profile.json").write_text(json.dumps(profile))
    (base / "shell.qml").write_text(QML)
    result = subprocess.run(["qs", "-p", str(base / "shell.qml"), "--no-color"], text=True, capture_output=True, timeout=20)
    output = result.stdout + result.stderr
    lines = [line.split("REGRESSION_RESULT ", 1)[1] for line in output.splitlines() if "REGRESSION_RESULT " in line]
    if not lines:
        raise AssertionError(output)
    verdict = json.loads(lines[-1])
    assert result.returncode == 0 and verdict["ok"], (verdict, output)
    calls = [json.loads(line) for line in (base / "calls.jsonl").read_text().splitlines()]
    assert [c["hardware"]["dpi"] for c in calls] == ["3200", "1000", "1050", "1050"], calls
    assert verdict["closed"] and verdict["finalDpi"] == "1050", verdict
    print("PASS: debounce, latest queued edit, busy dismissal/reopen, background completion, failure without retry loop and explicit retry (actual QML + simulated CLI).")
