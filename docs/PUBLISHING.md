# Publishing Omalogi

Repository: https://github.com/AlejandroFloresArroyo/omalogi

Plugin ID: `omalogi.mouse`. First release: `v0.1.0-beta.1`.

## Before publishing

1. Run the README's validation commands. Keep `Cargo.toml`, `Cargo.lock`, `manifest.json` and CHANGELOG versions aligned.
2. Complete a real new graphical session: confirm the service starts and physically test a gesture and wheel action without a manual restart. Record the result in VALIDATION.md.
3. Test installation/update/removal on a separate clean Omarchy account or machine. Confirm Solaar dependency installation, receiver access, widget discovery, retained unrelated settings and mouse restoration.
4. Review the public Git diff. Do not commit local profiles, logs, device artifacts, build output, the inspected Solaar checkout or reference-image directories; `.gitignore` excludes those paths.

## Push and create the release

```bash
git push -u origin main
git tag v0.1.0-beta.1
git push origin v0.1.0-beta.1
```

The Checks workflow validates Rust, Python transaction/installer contracts and distribution metadata. The Release workflow repeats the tests, builds a Linux x86_64 musl binary and creates a **draft prerelease** with the archive and its SHA256 checksum. The source checkout remains usable via `--from-source` before release publication. The tag must match the manifest version; mismatches stop the workflow.

Open the draft on GitHub, inspect its assets and publish it after validation. A draft release's assets cannot be downloaded by the public installer. The build dependencies remain in CI; users of the published binary need Solaar and the desktop, not Rust.

To exercise the packaging locally with a native development binary:

```bash
cargo build --release --locked
python3 scripts/package-release.py --binary target/release/omalogi --target x86_64-unknown-linux-gnu
```

Do not publish that local development archive under the musl asset name. The public installer selects `omalogi-vVERSION-x86_64-unknown-linux-musl.tar.gz` and verifies its companion `.sha256` file. Additional architectures require their own build and compatibility validation before adding them to the installer.

## Marketplace submission

The [Omarchy Plugins publishing guide](https://plugins.omarchy.org/publish.html) requires a public GitHub repository, valid root `manifest.json`, author, README, license and safe setup/removal. A preview image is optional.

Submit through the [plugin issue form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml), using:

- **Name:** Omalogi
- **Repository:** https://github.com/AlejandroFloresArroyo/omalogi
- **Description:** Logitech mouse controls for Omarchy: configure DPI, gestures, buttons, and scroll wheels through a native desktop panel.
- **Category:** Hardware, or the nearest category offered by the form.
- **Suggested tags:** logitech, mouse, mx-master, bolt, gestures, hardware.
- **Preview:** `docs/preview.png`, captured with simulated device data and an opaque staging background.
- **Compatibility:** MX Master 3S via Bolt; Omarchy 4.0.4, Quickshell 0.3.1, Hyprland 0.56.2, Solaar 1.1.20.
- **Setup:** `omarchy plugin add` followed by the checkout's `scripts/install.sh` to provision its backend.
- **Removal:** run the checkout's `scripts/uninstall.sh` first so the original mouse settings are restored.

The marketplace checks a specific commit; updates may require another submission for verification. Registry publication is separate from GitHub release publication. Do not claim clean-machine or new-session verification before it has actually been completed.
