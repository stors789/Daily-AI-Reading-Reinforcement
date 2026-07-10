#!/usr/bin/env python3
"""Fast structural validation for the Android foundation; no Android SDK required."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *snippets: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in text]
    if missing:
        raise AssertionError(f"{path} is missing: {missing}")


def main() -> None:
    require("settings.gradle.kts", 'include(":app")')
    require(
        "app/build.gradle.kts",
        "prepareSharedWebUi",
        "addon/daily_ai_reading_reinforcement/web",
        "AndroidDairrBridge.send",
        "assets.srcDir(generatedWebAssets)",
    )
    require(
        "app/src/main/java/com/dairr/android/MainActivity.kt",
        "addJavascriptInterface",
        "LocalOnlyWebViewClient",
        "WebViewAssetLoader",
        "https://appassets.androidplatform.net/assets/dairr/index.html",
        "allowContentAccess = false",
    )
    require(
        "app/src/main/java/com/dairr/android/bridge/BridgeContract.kt",
        "window.__DAIRR_BRIDGE__.send(action, payload)",
        "window.DAIRR.receive({ event, payload })",
        "supportedActions",
    )
    require(
        "app/src/main/java/com/dairr/android/security/CredentialStore.kt",
        "interface CredentialStore",
        "class DisabledCredentialStore",
        "UnsupportedOperationException",
    )
    print("Android shell scaffold validation passed.")


if __name__ == "__main__":
    main()
