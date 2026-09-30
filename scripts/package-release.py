"""Create a reproducible binary release with its license and SHA256 checksum."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import gzip

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', type=Path, required=True)
parser.add_argument('--target', default='x86_64-unknown-linux-musl')
parser.add_argument('--output', type=Path, default=ROOT / 'dist')
args = parser.parse_args()
version = json.loads((ROOT / 'manifest.json').read_text())['version']
assert subprocess.check_output([str(args.binary.resolve()), '--version'], text=True).strip() == f'omalogi {version}'
args.output.mkdir(parents=True, exist_ok=True)
asset = args.output / f'omalogi-v{version}-{args.target}.tar.gz'
with asset.open('wb') as output, gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as compressed:
    with tarfile.open(fileobj=compressed, mode='w') as archive:
        for name, path in [('omalogi', args.binary), ('LICENSE', ROOT / 'LICENSE')]:
            data = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755 if name == 'omalogi' else 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
checksum = hashlib.sha256(asset.read_bytes()).hexdigest()
asset.with_name(asset.name + '.sha256').write_text(f'{checksum}  {asset.name}\n')
print(asset)
