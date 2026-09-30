#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
config_root=${XDG_CONFIG_HOME:-"$HOME/.config"}
if [[ -f "$config_root/omalogi/state.json" ]]; then
  "$HOME/.local/bin/omalogi" restore
fi
omarchy plugin disable omalogi.mouse
systemctl --user disable --now omalogi-solaar.service
plugin_mode=$(python3 "$project_dir/scripts/install-files.py" uninstall "$project_dir")
systemctl --user daemon-reload
# Run this last: removing a git checkout also removes the script being executed.
if [[ $plugin_mode == git ]]; then
  omarchy plugin remove omalogi.mouse --yes
else
  omarchy-shell shell rescanPlugins
fi
echo 'Omalogi desinstalado. Solaar, perfiles, respaldos y registros se conservaron.'
