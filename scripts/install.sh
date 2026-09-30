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
    --binary) [[ $# -ge 2 ]] || { echo 'Falta la ruta de --binary' >&2; exit 1; }; binary=$2; shift 2 ;;
    -h|--help)
      echo 'Uso: bash scripts/install.sh [--from-source] [--offline] [--binary /ruta/omalogi]'
      echo 'Por defecto descarga el binario de la release correspondiente al manifiesto.'
      exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; exit 1 ;;
  esac
done
(( !from_source )) || [[ -z $binary ]] || { echo 'Elige --from-source o --binary' >&2; exit 1; }
(( EUID != 0 )) || { echo 'Ejecuta el instalador como tu usuario de escritorio, sin sudo.' >&2; exit 1; }
for command in omarchy omarchy-shell python3 systemctl; do
  command -v "$command" >/dev/null || { echo "Falta la dependencia: $command" >&2; exit 1; }
done
# The official plugin installer/host currently discover plugins under this exact location.
[[ ${XDG_CONFIG_HOME:-"$HOME/.config"} == "$HOME/.config" ]] || {
  echo 'Esta versión de Omarchy descubre plugins en ~/.config; XDG_CONFIG_HOME personalizado no está soportado por el instalador.' >&2; exit 1;
}
omarchy plugin validate "$project_dir"
if ! command -v solaar >/dev/null; then
  (( !offline )) || { echo 'Instala Solaar antes de usar --offline: omarchy pkg add solaar' >&2; exit 1; }
  omarchy pkg add solaar
fi
# The scalar adapter depends on internal APIs; accept only the version tested for this beta.
python3 - <<'PY'
import solaar, yaml
from solaar.cli import _find_device, _receivers_and_devices
if solaar.__version__ != '1.1.20':
    raise SystemExit(f'Solaar {solaar.__version__} no está validado para esta beta; versión probada: 1.1.20')
PY
version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$project_dir/manifest.json")
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$ ]] || { echo 'Versión de release inválida' >&2; exit 1; }
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
      echo 'La migración de archivos terminó; vuelve a ejecutar el instalador para completar el arranque de Omalogi.' >&2
    fi
  fi
  if (( result != 0 && current_stopped )); then
    systemctl --user start omalogi-solaar.service || true
  fi
  [[ -z $temporary_dir ]] || rm -rf -- "$temporary_dir"
}
trap cleanup EXIT
if (( from_source )); then
  command -v cargo >/dev/null || { echo 'Para compilar instala Rust: omarchy pkg add rust' >&2; exit 1; }
  cargo_args=(build --release --locked --manifest-path "$project_dir/Cargo.toml")
  (( !offline )) || cargo_args+=(--offline)
  cargo "${cargo_args[@]}"
  binary="$project_dir/target/release/omalogi"
elif [[ -z $binary ]]; then
  [[ $(uname -m) == x86_64 ]] || { echo 'La beta precompilada soporta x86_64. Otros equipos requieren --from-source y validación propia.' >&2; exit 1; }
  for command in curl tar sha256sum; do
    command -v "$command" >/dev/null || { echo "Falta la dependencia: $command" >&2; exit 1; }
  done
  (( !offline )) || { echo 'Usa --binary o --from-source con --offline.' >&2; exit 1; }
  temporary_dir=$(mktemp -d)
  asset="omalogi-v${version}-x86_64-unknown-linux-musl.tar.gz"
  base="https://github.com/AlejandroFloresArroyo/omalogi/releases/download/v${version}"
  curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 "$base/$asset" -o "$temporary_dir/$asset"
  curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 "$base/$asset.sha256" -o "$temporary_dir/$asset.sha256"
  (cd "$temporary_dir" && sha256sum --check --status "$asset.sha256") || { echo 'El checksum del binario no coincide.' >&2; exit 1; }
  tar -xzf "$temporary_dir/$asset" -C "$temporary_dir" -- omalogi
  binary="$temporary_dir/omalogi"
fi
binary=$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$binary")
[[ -x $binary && ! -L $binary ]] || { echo 'No se encontró un ejecutable regular de Omalogi.' >&2; exit 1; }
[[ $("$binary" --version) == "omalogi $version" ]] || { echo 'La versión del binario no coincide con la del plugin.' >&2; exit 1; }
python3 "$project_dir/scripts/install-files.py" preflight "$project_dir" --binary "$binary"
if [[ -f "$HOME/.config/omarchy-logi/install.json" ]]; then
  legacy_stopped=1
  if systemctl --user is-enabled --quiet omarchy-logi-solaar.service; then legacy_enabled=1; fi
  systemctl --user disable --now omarchy-logi-solaar.service
elif systemctl --user is-active --quiet omalogi-solaar.service; then
  systemctl --user stop omalogi-solaar.service
  current_stopped=1
elif pgrep -x solaar >/dev/null; then
  echo 'Solaar está abierto fuera del servicio de Omalogi. Ciérralo y vuelve a instalar.' >&2; exit 1
fi
python3 "$project_dir/scripts/install-files.py" install "$project_dir" --binary "$binary"
systemctl --user daemon-reload
systemctl --user enable --now omalogi-solaar.service
systemctl --user is-active --quiet omalogi-solaar.service
omarchy-shell shell rescanPlugins
omarchy plugin enable omalogi.mouse --section right
echo 'Omalogi instalado. Abre: ~/.local/bin/omalogi panel'
