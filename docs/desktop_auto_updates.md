# DAIRR desktop automatic updates

The desktop release pipeline is designed around the official Tauri v2 updater.
A release build with an injected public key and updater endpoint can check the
static `latest.json` attached to a GitHub Release, verify its Tauri signature,
ask the user in a native dialog, install the matching package, and restart
DAIRR. The checked-in development configuration intentionally contains no
active updater key or endpoint, so source/dev builds must not be described as
receiving production updates. The browser launcher and Anki add-on are outside
this update path.

No update is considered production-verified until a signed test release has
successfully upgraded an installed macOS and Windows build while preserving
local config, article history, and practice history.

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
- `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, and `KEYCHAIN_PASSWORD`:
  Developer ID Application certificate import. The workflow derives
  `APPLE_SIGNING_IDENTITY` from that imported certificate and exports it only
  for the build; it is not a separate repository secret.
- `APPLE_ID`, `APPLE_PASSWORD`, and `APPLE_TEAM_ID`: the Apple-ID/app-specific
  password notarization method currently implemented by this workflow. API-key
  notarization is not claimed unless the workflow is extended to materialize
  `APPLE_API_KEY_PATH` securely and supply the matching key and issuer.
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
