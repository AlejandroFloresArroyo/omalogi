#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
from_source=0
offline=0
binary=""
while (( $# )); do
  case "$1" in
    --from-source) from_source=1; shift ;;
    --offline) offline=1; shift ;;
    --binary) [[ $# -ge 2 ]] || { echo 'Missing path for --binary' >&2; exit 1; }; binary=$2; shift 2 ;;
    -h|--help)
      echo 'Usage: bash scripts/install.sh [--from-source] [--offline] [--binary /path/to/omalogi]'
      echo 'By default, downloads the release binary matching the manifest.'
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done
(( !from_source )) || [[ -z $binary ]] || { echo 'Choose --from-source or --binary' >&2; exit 1; }
(( EUID != 0 )) || { echo 'Run the installer as your desktop user, without sudo.' >&2; exit 1; }
for command in omarchy omarchy-shell python3 systemctl; do
  command -v "$command" >/dev/null || { echo "Missing dependency: $command" >&2; exit 1; }
done
# The official plugin installer/host currently discover plugins under this exact location.
[[ ${XDG_CONFIG_HOME:-"$HOME/.config"} == "$HOME/.config" ]] || {
  echo 'This Omarchy version discovers plugins in ~/.config; the installer does not support a custom XDG_CONFIG_HOME.' >&2; exit 1;
}
omarchy plugin validate "$project_dir"
if ! command -v solaar >/dev/null; then
  (( !offline )) || { echo 'Install Solaar before using --offline: omarchy pkg add solaar' >&2; exit 1; }
  omarchy pkg add solaar
fi
# The scalar adapter depends on internal APIs; accept only the version tested for this beta.
python3 - <<'PY'
import solaar, yaml
from solaar.cli import _find_device, _receivers_and_devices
if solaar.__version__ != '1.1.20':
    raise SystemExit(f'Solaar {solaar.__version__} is not validated for this beta; tested version: 1.1.20')
PY
version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$project_dir/manifest.json")
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$ ]] || { echo 'Invalid release version' >&2; exit 1; }
temporary_dir=""
legacy_stopped=0
legacy_enabled=0
current_stopped=0
cleanup() {
  local result=$?
  if (( result != 0 && legacy_stopped )); then
    if [[ -f "$HOME/.config/omarchy-logi/install.json" ]]; then
      if (( legacy_enabled )); then
        systemctl --user enable --now omarchy-logi-solaar.service || true
      else
        systemctl --user start omarchy-logi-solaar.service || true
      fi
    else
      echo 'File migration finished; rerun the installer to complete Omalogi startup.' >&2
    fi
  fi
  if (( result != 0 && current_stopped )); then
    systemctl --user start omalogi-solaar.service || true
  fi
  [[ -z $temporary_dir ]] || rm -rf -- "$temporary_dir"
}
trap cleanup EXIT
if (( from_source )); then
  command -v cargo >/dev/null || { echo 'To build, install Rust: omarchy pkg add rust' >&2; exit 1; }
  cargo_args=(build --release --locked --manifest-path "$project_dir/Cargo.toml")
  (( !offline )) || cargo_args+=(--offline)
  cargo "${cargo_args[@]}"
  binary="$project_dir/target/release/omalogi"
elif [[ -z $binary ]]; then
  [[ $(uname -m) == x86_64 ]] || { echo 'The prebuilt beta supports x86_64. Other systems require --from-source and their own validation.' >&2; exit 1; }
  for command in curl tar sha256sum; do
    command -v "$command" >/dev/null || { echo "Missing dependency: $command" >&2; exit 1; }
  done
  (( !offline )) || { echo 'Use --binary or --from-source with --offline.' >&2; exit 1; }
  temporary_dir=$(mktemp -d)
  asset="omalogi-v${version}-x86_64-unknown-linux-musl.tar.gz"
  base="https://github.com/AlejandroFloresArroyo/omalogi/releases/download/v${version}"
  curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 "$base/$asset" -o "$temporary_dir/$asset"
  curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 "$base/$asset.sha256" -o "$temporary_dir/$asset.sha256"
  (cd "$temporary_dir" && sha256sum --check --status "$asset.sha256") || { echo 'The binary checksum does not match.' >&2; exit 1; }
  tar -xzf "$temporary_dir/$asset" -C "$temporary_dir" -- omalogi
  binary="$temporary_dir/omalogi"
fi
binary=$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$binary")
[[ -x $binary && ! -L $binary ]] || { echo 'No regular Omalogi executable was found.' >&2; exit 1; }
[[ $("$binary" --version) == "omalogi $version" ]] || { echo 'The binary version does not match the plugin version.' >&2; exit 1; }
python3 "$project_dir/scripts/install-files.py" preflight "$project_dir" --binary "$binary"
if [[ -f "$HOME/.config/omarchy-logi/install.json" ]]; then
  legacy_stopped=1
  if systemctl --user is-enabled --quiet omarchy-logi-solaar.service; then legacy_enabled=1; fi
  systemctl --user disable --now omarchy-logi-solaar.service
elif systemctl --user is-active --quiet omalogi-solaar.service; then
  systemctl --user stop omalogi-solaar.service
  current_stopped=1
elif pgrep -x solaar >/dev/null; then
  echo 'Solaar is running outside the Omalogi service. Close it and reinstall.' >&2; exit 1
fi
python3 "$project_dir/scripts/install-files.py" install "$project_dir" --binary "$binary"
systemctl --user daemon-reload
systemctl --user enable --now omalogi-solaar.service
systemctl --user is-active --quiet omalogi-solaar.service
omarchy-shell shell rescanPlugins
omarchy plugin enable omalogi.mouse --section right
echo 'Omalogi installed. Open: ~/.local/bin/omalogi panel'
