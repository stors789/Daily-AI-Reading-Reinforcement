# Tauri app-shell architecture

## Decision

DAIRR's preferred standalone desktop shell lives in `apps/desktop/` and uses
Tauri v2. Tauri owns the native process and window while the existing Python
backend remains the authority for providers, AnkiConnect, persistence,
generation, practice, scoring, and the shared web interface. This keeps the
standalone and Anki add-on paths on the same domain/application logic without
introducing Anki internals into the desktop process.

The browser launcher and pywebview launcher remain development and diagnostic
fallbacks. They do not provide evidence that a Tauri installer is releasable.

## Process boundary

The shell is intentionally thin:

- debug builds normally start `desktop_app.py` from the source checkout;
- release builds start a target-native PyInstaller sidecar bundled as a Tauri
  resource;
- `desktop_mock/main.py` serves the shared UI and authenticated loopback HTTP
  bridge;
- the backend injects `window.__DAIRR_BRIDGE__` and a high-entropy,
  per-process bridge token into the served page;
- provider credentials, AnkiConnect access, configuration, article history,
  and practice persistence stay in Python;
- Tauri owns the child process and sends an instance-specific authenticated
  shutdown request before applying its bounded termination fallback.

The production resource layout is an onedir runtime:

```text
binaries/
└── dairr-backend/
    ├── dairr-backend        # dairr-backend.exe on Windows
    └── _internal/           # PyInstaller runtime files
```

`apps/desktop/src-tauri/tauri.conf.json` includes
`binaries/dairr-backend` as a resource. The repository tracks only the empty
runtime directory marker and documentation. It does **not** contain an
executable or target-triple placeholder. Each macOS ARM64, macOS Intel, or
Windows x64 release job must generate its own target-native onedir runtime;
PyInstaller does not cross-compile. The `--target-triple` option selects the
expected runtime-entry convention and validates the requested target, but it
does not create a differently named checked-in executable.

The Rust launcher retains target-triple filename candidates only as a runtime
compatibility fallback for older locally built bundles. They are not the
current packaging contract.

## Backend modes

### Development backend

Debug builds default to the Python launcher:

```bash
python3 desktop_app.py --provider mock --host 127.0.0.1 --port 8755 --no-browser
```

Supported environment overrides include:

- `DAIRR_REPO_ROOT`: explicit source root for development;
- `DAIRR_PYTHON`: Python executable instead of `python3`;
- `DAIRR_DESKTOP_PROVIDER`: `mock`, `ankiconnect`, or `real_momo`;
- `DAIRR_ANKICONNECT_URL`: non-default AnkiConnect endpoint;
- `MOMO_TOKEN` or `Maimemo_key`: MoMo credential consumed by the Python
  provider;
- `DAIRR_BACKEND_MODE=dev` or `python`: force the development launcher.

### Production sidecar

Release builds default to the bundled sidecar. Tauri starts it with the same
public CLI plus shell-owned lifecycle values:

```text
dairr-backend --provider ankiconnect --host 127.0.0.1 --port 8755 \
  --no-browser --parent-pid <pid> --instance-id <random> \
  --shutdown-token <random>
```

`DAIRR_BACKEND_MODE=sidecar` (or `production`) forces this path in a debug
build. `DAIRR_BACKEND_SIDECAR=/absolute/path/to/dairr-backend` can select a
specific target-native onedir entry for testing.

The shell writes bounded operational diagnostics to the platform application
log directory. It does not put provider credentials, prompt bodies, or private
practice text into shell arguments or health responses.

## Startup and ownership checks

Port `8755` is a local singleton. Before spawning a backend, Tauri probes
`GET /api/health` with an exact loopback `Host`. Any existing listener causes
startup to stop: even another DAIRR instance is not silently reused.

After spawning, Tauri waits for a valid response whose `instanceId` matches
the fresh value passed to that child. The response must also have HTTP 200,
valid JSON, `app == "DAIRR"`, and `bridge.available == true`. This prevents an
unrelated service or stale DAIRR process from being treated as the owned
backend.

A representative health response is:

```json
{
  "app": "DAIRR",
  "name": "Daily AI Reading Reinforcement",
  "version": "0.1.0",
  "mode": "desktop",
  "provider": "ankiconnect",
  "instanceId": "instance-...",
  "parentPid": 12345,
  "bridge": {
    "available": true,
    "type": "http",
    "protocolVersion": 2,
    "endpoint": "/api/bridge",
    "windowObject": "__DAIRR_BRIDGE__",
    "tokenRequired": true,
    "maxRequestBytes": 2000000
  }
}
```

Health confirms process identity and bridge availability; it does not prove
that Anki or a remote model provider is connected.

## Authenticated loopback bridge

The backend accepts bridge traffic only on loopback and validates the request
`Host`. A browser-originated POST must use one of the exact origins for the
active port, such as `http://127.0.0.1:8755`, and every bridge POST must include
the per-process token in `X-DAIRR-Bridge-Token`. JSON is mandatory and request
bodies have an explicit size limit. The served page applies no-store and
restrictive content-security headers.

The token is injected into the page as `window.__DAIRR_BRIDGE_TOKEN__`; it is
not returned from `/api/health`, written to configuration, or a substitute for
an operating-system sandbox. Normal UI code should call the injected bridge
instead of handling the token directly.

For a local manual smoke test with disposable data, obtain the current process
token from the locally served page and send both required headers:

```bash
BRIDGE_TOKEN="$(curl -fsS http://127.0.0.1:8755/ | python3 -c 'import re,sys; page=sys.stdin.read(); match=re.search(r"window\.__DAIRR_BRIDGE_TOKEN__ = \"([0-9A-Za-z_-]+)\"", page); print(match.group(1) if match else "")')"
test -n "$BRIDGE_TOKEN"

curl -X POST http://127.0.0.1:8755/api/bridge \
  -H 'Origin: http://127.0.0.1:8755' \
  -H 'Content-Type: application/json' \
  -H "X-DAIRR-Bridge-Token: $BRIDGE_TOKEN" \
  -d '{"version":2,"requestId":"manual-smoke-1","action":"load","payload":{}}'
```

Omitting the token returns HTTP 403. An origin from outside the exact loopback
allow-list is rejected before dispatch.

## Build and verification

From the repository root, build the onedir runtime on the target operating
system and architecture:

```bash
# Auto-detect the current target.
python3 package_tauri_sidecar.py --clean

# These commands must run on their named native targets.
python3 package_tauri_sidecar.py --target-triple x86_64-apple-darwin --clean
python3 package_tauri_sidecar.py --target-triple x86_64-pc-windows-msvc --clean

# Inspect the command or verify the generated runtime entry.
python3 package_tauri_sidecar.py --dry-run
python3 package_tauri_sidecar.py --check-placeholder
```

Despite the legacy option name, `--check-placeholder` now serves as a release
guard: because no placeholder executable is checked in, it fails until a real
generated runtime entry exists and rejects a small placeholder-like file.

Start and verify a generated sidecar:

```bash
./apps/desktop/src-tauri/binaries/dairr-backend/dairr-backend \
  --provider mock --host 127.0.0.1 --port 8755 --no-browser

curl http://127.0.0.1:8755/api/health
```

Use the authenticated bridge example above for POST verification. Then test
the native shell:

```bash
cd apps/desktop
npm install
DAIRR_BACKEND_MODE=sidecar npm run dev
```

The consolidated credential-free gate is:

```bash
python3 scripts/desktop_release.py pre-publish
```

That gate checks source/configuration, tests, UI syntax, Android static
validation, packaging dry-runs, and locked Rust compilation. It does not build
or certify signed installers for an operating system other than the runner.

## Android boundary

Android uses the shared bridge-v2 UI contract behind a native allow-listed
adapter rather than this loopback Python server. The current Android edge
supports app-private offline pasted-text practice; provider-backed AI review,
article history, Anki data, scoring, prompts, and reasoning remain explicit
unavailable capabilities. Shared HTML therefore does not imply desktop feature
parity.

## Release evidence and remaining risks

- A release job must build a fresh sidecar natively and verify the runtime
  entry before invoking Tauri. Repository state alone contains no executable.
- macOS ARM64 and Intel artifacts require their respective native build
  evidence. Public distribution additionally requires Developer ID signing,
  notarization, stapling, and installed-app verification.
- Windows x64 requires a native build, NSIS installer verification,
  Authenticode/timestamping, WebView2 behavior checks, and installed-app smoke
  testing. A macOS run cannot prove these properties.
- Updater signatures are independent of macOS/Windows code signing. Checked-in
  updater configuration remains credential-free; release jobs inject public
  metadata and signing material without committing secrets.
- The fixed local port prevents concurrent desktop instances. Ownership checks
  fail closed rather than attaching to an existing process.
- Generated `binaries/dairr-backend/` contents, PyInstaller work trees, and
  release artifacts are ignored and must not be committed.
- Live MoMo/OpenAI-compatible and AnkiConnect behavior still requires
  disposable credentials and environment-specific manual verification.

See [desktop shells](../native_shell.md), [packaging](../packaging.md),
[automatic updates](../desktop_auto_updates.md), and the
[manual verification guide](../manual-verification.md).
