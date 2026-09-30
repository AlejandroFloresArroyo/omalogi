"""Manage Omalogi's files and migrate the local MVP without touching HID settings."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile

PLUGIN_ID = "omalogi.mouse"
LEGACY_APP = "omarchy-logi"
LEGACY_PLUGIN = "local.logi"
LEGACY_QML = {"LogiWidget.qml", "LogiPanel.qml", "ActionRow.qml", "MouseBinding.qml", "MouseDiagram.qml"}
QML = {"OmalogiWidget.qml", "OmalogiPanel.qml", "ActionRow.qml", "MouseBinding.qml", "MouseDiagram.qml"}


def atomic(path, content, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".omalogi-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Installation:
    def __init__(self, project, binary=None):
        self.project = Path(project).resolve()
        self.binary = Path(binary).resolve() if binary else self.project / "target/release/omalogi"
        self.home = Path.home()
        self.config = Path(os.environ.get("XDG_CONFIG_HOME", self.home / ".config"))
        self.app = self.config / "omalogi"
        self.legacy = self.config / LEGACY_APP
        self.plugin = self.config / "omarchy/plugins" / PLUGIN_ID
        self.service = self.config / "systemd/user/omalogi-solaar.service"
        self.desktop = self.home / ".local/share/applications/omalogi.desktop"
        self.native = self.project == self.plugin.resolve()
        self.backend_paths = {self.home / ".local/bin/omalogi", self.service, self.desktop}
        self.plugin_paths = {self.plugin / "manifest.json"} | {self.plugin / "plugin" / n for n in QML}
        self.allowed = self.backend_paths | self.plugin_paths
        self.legacy_paths = {
            self.home / ".local/bin" / LEGACY_APP,
            self.config / "systemd/user" / f"{LEGACY_APP}-solaar.service",
            self.home / ".local/share/applications" / f"{LEGACY_APP}.desktop",
        } | {self.config / "omarchy/plugins" / LEGACY_PLUGIN / n for n in LEGACY_QML | {"manifest.json"}}

    @staticmethod
    def receipt(path, allowed):
        data = json.loads(path.read_text()) if path.exists() else {"files": []}
        if not isinstance(data.get("files"), list) or any(not isinstance(n, str) or Path(n) not in allowed for n in data["files"]):
            raise ValueError(f"Registro de instalación con rutas desconocidas: {path}")
        return data

    def preflight(self):
        migrating = (self.legacy / "install.json").exists()
        if migrating and self.app.exists():
            raise ValueError("Hay dos directorios de configuración. Conserva ambos y resuelve el conflicto antes de migrar")
        if self.legacy.exists() and not migrating:
            raise ValueError("Hay configuración anterior sin registro de instalación; no se migra automáticamente")
        old = self.receipt(self.legacy / "install.json" if migrating else self.app / "install.json",
                           self.legacy_paths if migrating else self.allowed)
        if not self.native and (self.plugin / ".git").exists():
            raise ValueError("Ejecuta el instalador desde el checkout del plugin instalado para conservar sus actualizaciones Git")
        if self.native and (old.get("pluginMode") == "copy"):
            raise ValueError("El registro pertenece a una instalación desde fuentes; reinstálala desde el checkout original")
        targets = self.backend_paths | (set() if self.native else self.plugin_paths)
        for path in targets:
            if path.is_symlink() or (path.exists() and str(path) not in old["files"]):
                raise ValueError(f"No se sobrescribe un archivo preexistente ajeno: {path}")
            if any(p.is_symlink() for p in path.parents if p != self.home and p != self.config):
                raise ValueError(f"No se instala a través de un enlace simbólico: {path}")
        # Read every input before the first write.
        sources = {self.home / ".local/bin/omalogi": self.binary}
        if not self.native:
            sources[self.plugin / "manifest.json"] = self.project / "manifest.json"
            sources.update({self.plugin / "plugin" / n: self.project / "plugin" / n for n in QML})
        contents = {target: source.read_bytes() for target, source in sources.items()}
        if migrating:
            state = self.legacy / "state.json"
            if state.exists() and json.loads(state.read_text()).get("pending"):
                raise ValueError("Hay una operación pendiente. Restaura el mouse con la CLI anterior antes de migrar")
            self.migrated_rules()  # Reject malformed managed blocks before stopping services.
        return migrating, old, contents

    def migrated_rules(self):
        path = self.config / "solaar/rules.yaml"
        if not path.exists():
            return None
        text = path.read_text()
        begin, end = "# BEGIN OMARCHY-LOGI v1\n", "# END OMARCHY-LOGI v1\n"
        if begin not in text and end not in text:
            return None
        if text.count(begin) != 1 or text.count(end) != 1 or not text.startswith(begin) or "# BEGIN OMALOGI" in text or "# END OMALOGI" in text:
            raise ValueError("Bloque anterior de reglas dañado; no se modifica")
        boundary = text.index(end) + len(end)
        block, outside = text[:boundary], text[boundary:]
        # Only rewrite the managed block; foreign bytes and hardware persistence stay untouched.
        block = block.replace(begin, "# BEGIN OMALOGI v1\n").replace(end, "# END OMALOGI v1\n")
        block = block.replace(json.dumps(str(self.home / ".local/bin" / LEGACY_APP)),
                              json.dumps(str(self.home / ".local/bin/omalogi")))
        return path, (block + outside).encode()

    def install(self):
        migrating, old, contents = self.preflight()
        lock_root = self.legacy if migrating else self.app
        lock_root.mkdir(parents=True, exist_ok=True)
        with (lock_root / "operation.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            # Check again while holding the same lock as apply/restore.
            migrating, old, contents = self.preflight()
            if migrating:
                # An in-flight old CLI may have restarted it before releasing this lock.
                subprocess.run(["systemctl", "--user", "stop", f"{LEGACY_APP}-solaar.service"], check=True)
            changed = {}
            moved = False
            def write(path, content, mode=0o644):
                if path not in changed:
                    changed[path] = (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None
                atomic(path, content, mode)
            try:
                if migrating:
                    self.legacy.rename(self.app)
                    moved = True
                    write(self.app / "legacy-install.json", json.dumps(old, indent=2).encode(), 0o600)
                shell = self.config / "omarchy/shell.json"
                backup = self.app / "shell-before-install.json"
                if shell.exists() and not backup.exists():
                    write(backup, shell.read_bytes(), 0o600)
                for target, content in contents.items():
                    write(target, content, 0o755 if target == self.home / ".local/bin/omalogi" else 0o644)
                write(self.service, b'''[Unit]
Description=Solaar event capture for Omalogi
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/solaar --window=hide
Restart=on-failure
RestartSec=3
TimeoutStopSec=10

[Install]
WantedBy=graphical-session.target
''')
                executable = str(self.home / ".local/bin/omalogi").replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
                write(self.desktop, f'''[Desktop Entry]
Type=Application
Name=Omalogi
Comment=Logitech mouse controls for Omarchy
Exec="{executable}" panel
Icon=input-mouse
Terminal=false
Categories=Settings;HardwareSettings;
'''.encode())
                managed = sorted(str(p) for p in self.backend_paths | (set() if self.native else self.plugin_paths))
                write(self.app / "install.json", json.dumps({"version": 2, "files": managed,
                    "pluginMode": "git" if self.native else "copy"}, indent=2).encode(), 0o600)
                if migrating:
                    rules = self.migrated_rules()
                    if rules:
                        write(*rules, 0o600)
                    if shell.exists():
                        def rename(value):
                            if isinstance(value, dict):
                                return {k: PLUGIN_ID if k == "id" and v == LEGACY_PLUGIN else rename(v) for k, v in value.items()}
                            if isinstance(value, list):
                                return [rename(v) for v in value]
                            return value
                        write(self.app / "shell-before-migration.json", shell.read_bytes(), 0o600)
                        write(shell, json.dumps(rename(json.loads(shell.read_text())), indent=2).encode())
                    # Removing a file is also journaled for rollback.
                    for name in old["files"]:
                        path = Path(name)
                        if path.exists():
                            changed[path] = (path.read_bytes(), path.stat().st_mode & 0o777)
                            path.unlink()
                    legacy_plugin = self.config / "omarchy/plugins" / LEGACY_PLUGIN
                    if legacy_plugin.exists() and not any(legacy_plugin.iterdir()):
                        legacy_plugin.rmdir()
            except Exception:
                for path, previous in reversed(list(changed.items())):
                    if previous is None:
                        path.unlink(missing_ok=True)
                    else:
                        atomic(path, *previous)
                if moved:
                    self.app.rename(self.legacy)
                raise

    def uninstall(self):
        path = self.app / "install.json"
        if not path.exists():
            raise ValueError("No hay una instalación administrada")
        with (self.app / "operation.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            receipt = self.receipt(path, self.allowed)
            for name in receipt["files"]:
                Path(name).unlink(missing_ok=True)
            for folder in [self.plugin / "plugin", self.plugin]:
                if folder.exists() and not any(folder.iterdir()):
                    folder.rmdir()
            path.unlink()
            print(receipt.get("pluginMode", "copy"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["preflight", "install", "uninstall"])
    parser.add_argument("project")
    parser.add_argument("--binary")
    args = parser.parse_args()
    install = Installation(args.project, args.binary)
    try:
        getattr(install, args.operation)()
    except (ValueError, OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
