# DAIRR desktop automatic updates

The packaged macOS and Windows app uses the official Tauri v2 updater. It
checks the static `latest.json` attached to the latest GitHub Release, verifies
the Tauri updater signature, asks the user in a native dialog, downloads the
matching package, installs it, and restarts DAIRR. The browser launcher and
Anki add-on are intentionally outside this update path.

## Release inputs

`apps/desktop/release.json` is the checked-in source of truth for the desktop
version and static updater endpoint. Run this before opening a release PR:

```bash
python3 scripts/desktop_release.py sync-version --version 0.1.1
python3 scripts/desktop_release.py verify
```

Release builds must have a Tauri updater key pair. Generate it once in an
offline, access-controlled environment and store the **private** key in a
durable secret manager; do not commit it or rotate it casually:

```bash
cd apps/desktop
npm run tauri signer generate -- -w ~/.tauri/dairr-updater.key
```

Configure these repository secrets before pushing a signed `vX.Y.Z` tag:

- `TAURI_UPDATER_PRIVATE_KEY`: updater private-key contents (or a secure file
  path supported by the build environment).
- `TAURI_UPDATER_PRIVATE_KEY_PASSWORD`: key password, if one was set.
- `TAURI_UPDATER_PUBLIC_KEY`: corresponding public-key contents. This is not
  confidential, but is injected only into the release configuration so source
  builds cannot accidentally target an unconfigured updater.
- `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `KEYCHAIN_PASSWORD`, and
  `APPLE_SIGNING_IDENTITY`: Developer ID Application signing certificate setup.
- One notarization method: `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`; or
  `APPLE_API_ISSUER`, `APPLE_API_KEY`, and `APPLE_API_KEY_PATH` (the workflow
  writes the API key secret to a temporary file when that method is adopted).
- `WINDOWS_CERTIFICATE`, `WINDOWS_CERTIFICATE_PASSWORD`,
  `WINDOWS_CERTIFICATE_THUMBPRINT`, and `WINDOWS_TIMESTAMP_URL`: Authenticode
  `.pfx` material and timestamp service for the NSIS installer.

The updater signature key is independent of Apple and Authenticode signing. If
the updater private key is lost, already-installed DAIRR versions cannot trust
future updates signed by a new key. Tauri updater verification cannot be
disabled.

## What the release workflow produces

`.github/workflows/release-desktop.yml` only runs on a `v*` tag after the tag
version is validated. It builds the Python sidecar natively—never with
cross-compilation—on macOS ARM64, macOS Intel, and Windows x64. It then builds
only DMG/macOS updater archives and NSIS Windows installers. The static
manifest contains all three platform records, their individual signatures, and
HTTPS GitHub Release URLs.

Use an actual test release (`v0.1.0-test.1`, for example) to verify a full
upgrade before marking a public release latest. Confirm that data in the DAIRR
application directory and saved history remain after update; updater packages
replace application files, not user data.

## macOS and Windows release requirements

macOS production releases need a paid Apple Developer account, Developer ID
Application signing, and notarization. An ad-hoc signature is useful only for
development and still leads to user warnings. Windows production releases need
an Authenticode certificate (ideally EV or cloud-backed) and a timestamped
signature; unsigned packages trigger SmartScreen reputation warnings.

The workflow intentionally fails rather than publish unsigned updater artifacts
when these credentials are absent. See the official [Tauri updater guide](https://v2.tauri.app/plugin/updater/), [macOS signing guide](https://v2.tauri.app/distribute/sign/macos/), and [Windows signing guide](https://v2.tauri.app/distribute/sign/windows/).
