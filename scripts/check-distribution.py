"""Check the contract shared by GitHub releases, Cargo and the Omarchy catalog."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--tag')
args = parser.parse_args()
manifest = json.loads((ROOT / 'manifest.json').read_text())
cargo = (ROOT / 'Cargo.toml').read_text()
version = re.search(r'^version = "([^"]+)"', cargo, re.M)[1]
assert manifest['version'] == version, 'Cargo and manifest versions differ'
locked_version = re.search(r'name = "omalogi"\nversion = "([^"]+)"', (ROOT / 'Cargo.lock').read_text())[1]
assert locked_version == version, 'Cargo.lock version differs'
assert manifest['schemaVersion'] == 1 and type(manifest['schemaVersion']) is int
assert manifest['id'] == 'omalogi.mouse'
assert manifest['name'] == 'Omalogi' and manifest['author']
assert manifest['kinds'] == ['bar-widget']
assert manifest['entryPoints']['barWidget'] == 'plugin/OmalogiWidget.qml'
assert (ROOT / manifest['entryPoints']['barWidget']).is_file()
assert not (ROOT / 'plugin/manifest.json').exists(), 'Only the root manifest should be shipped'
for name in ['README.md', 'LICENSE', 'CHANGELOG.md', 'docs/PUBLISHING.md']:
    assert (ROOT / name).is_file(), name
if args.tag:
    assert args.tag == f'v{version}', f'Tag must be v{version}'
print(f'Omalogi {version}: distribution metadata OK')
