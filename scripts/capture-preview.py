"""Capture the real native popup using simulated device data, without HID access."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dpi', default='1000')
parser.add_argument('--page', choices=['Mouse', 'Extras'], default='Mouse')
parser.add_argument('--transport', default='Bolt')
parser.add_argument('--output', type=Path, default=ROOT/'docs/preview.png')
args = parser.parse_args()
FAKE = '''#!/usr/bin/python3
import json,sys
from pathlib import Path
base=Path(__file__).parent
if sys.argv[1]=='geometry':
 (base/'geometry.json').write_text(sys.argv[2])
 print('{"ok":true}')
else:
 print((base/'status.json').read_text())
'''
QML = '''import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "plugin"
ShellRoot {
    id: shell
    property int ticks: 0
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
        // Opaque staging surface keeps the user's desktop out of the public image.
        screen: Quickshell.screens[0]
        visible: true
        anchors { top: true; bottom: true; left: true; right: true }
        color: "#181818"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.namespace: "omalogi-preview-background"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    }
    PanelWindow {
        screen: Quickshell.screens[0]; visible: false
        anchors { top: true; left: true; right: true }
        implicitHeight: 26
        OmalogiWidget { id: widget; bar: bar }
    }
    Process { id: geometry }
    Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
            shell.ticks++
            if (shell.ticks === 1) widget.open()
            var p = widget.children[1]
            if (shell.ticks > 12 && p.profile && !p.busy) {
                geometry.command = [p.binary, "geometry", JSON.stringify({
                    x:p.screen.x+p.cardOrigin.x, y:p.screen.y+p.cardOrigin.y,
                    width:p.contentWidth,height:p.contentHeight
                })]
                geometry.running = true
                running = false
            }
        }
    }
}
'''
profile = {
    'version': 1, 'device_id': 'PREVIEW', 'device_name': 'MX Master 3S',
    'hardware': {'dpi':args.dpi, 'scroll-ratchet':'Ratcheted', 'smart-shift':'10',
                 'hires-smooth-invert':'false', 'hires-smooth-resolution':'false', 'thumb-scroll-invert':'false'},
    'bindings': {e:'native' for e in ['gesture.click','gesture.up','gesture.down','gesture.left','gesture.right',
                 'button.back','button.forward','wheel.up','wheel.down','thumb.left','thumb.right']},
    'wheel_interval_ms': 120,
}
profile['bindings'].update({'gesture.click':'apps','gesture.up':'menu','gesture.down':'scratchpad',
                            'gesture.left':'workspace.previous','gesture.right':'workspace.next'})
settings = {key:{'value':value,'choices':[str(n) for n in range(200,8001,50)] if key=='dpi' else ['Ratcheted','Freespinning'],
                 'toggle':value in ('true','false')} for key,value in profile['hardware'].items()}
actions = [{'id':key,'label':value} for key,value in [
    ('native','Default behavior'), ('none','No action'), ('apps','Applications'), ('menu','Omarchy menu'),
    ('scratchpad','Scratchpad'), ('workspace.previous','Previous workspace'), ('workspace.next','Next workspace')]]
status = {'ok':True,'devices':[{'id':'PREVIEW','name':'MX Master 3S','transport':args.transport,'settings':settings}], 'config':profile,
          'actions':actions,'events':[],'applied':True,'pending':False,'daemon':True}
with tempfile.TemporaryDirectory(prefix='omalogi-preview-') as temp:
    base = Path(temp)
    for name in ['Ui','Commons']:
        (base/name).symlink_to(Path('/usr/share/omarchy/shell')/name, target_is_directory=True)
    (base/'plugin').mkdir()
    for src in (ROOT/'plugin').glob('*.qml'):
        text = src.read_text().replace('Quickshell.env("HOME") + "/.local/bin/omalogi"', json.dumps(str(base/'fake-cli')))
        (base/'plugin'/src.name).write_text(text)
    (base/'fake-cli').write_text(FAKE)
    (base/'fake-cli').chmod(0o755)
    (base/'status.json').write_text(json.dumps(status))
    (base/'shell.qml').write_text(QML.replace('var p = widget.children[1]', 'var p = widget.children[1]; p.page = ' + json.dumps(args.page)))
    with (base/'quickshell.log').open('w') as log:
        process = subprocess.Popen(['qs','-p',str(base/'shell.qml'),'--no-color'], stdout=log,stderr=log)
        try:
            deadline = time.monotonic()+20
            while not (base/'geometry.json').exists():
                if process.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError((base/'quickshell.log').read_text())
                time.sleep(.1)
            g = json.loads((base/'geometry.json').read_text())
            region = f"{g['x']},{g['y']} {g['width']}x{g['height']}"
            output = args.output
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['grim','-g',region,str(output)], check=True)
            print(output)
        finally:
            process.terminate()
            process.wait(timeout=5)
