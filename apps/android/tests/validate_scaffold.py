#!/usr/bin/env python3
"""Fast structural validation for the Android production edge; no SDK required."""

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
        "sendRequest: function(envelope)",
        "AndroidDairrBridge.sendRequest",
        "assets.srcDir(generatedWebAssets)",
    )
    require(
        "app/src/main/java/com/dairr/android/MainActivity.kt",
        "addJavascriptInterface",
        "LocalOnlyWebViewClient",
        "WebViewAssetLoader",
        "https://appassets.androidplatform.net/assets/dairr/index.html",
        "allowContentAccess = false",
        "domStorageEnabled = true",
        "AndroidBridgeDispatcher",
        "javascriptBridge?.destroy()",
        "Block external subresources",
    )
    require(
        "app/src/main/java/com/dairr/android/bridge/BridgeContract.kt",
        "window.__DAIRR_BRIDGE__.send(action, payload)",
        "window.DAIRR.receive({ event, payload })",
        "const val VERSION = 2",
        '"createPastedPractice"',
        '"savePracticeDraft"',
        '"updatePracticeSegments"',
        "supportedActions",
        "\"selectSource\"",
    )
    require(
        "app/src/main/java/com/dairr/android/bridge/BridgeDispatcher.kt",
        "class AndroidBridgeDispatcher",
        '"pasted_text_practice"',
        '"data_absent"',
        '"provider_unsupported"',
        "BridgeContract.failure",
        "shutdownNow()",
    )
    require(
        "app/src/main/java/com/dairr/android/practice/AndroidPracticeRepository.kt",
        "SCHEMA_VERSION = 2",
        "MAX_SOURCE_CHARACTERS = 50_000",
        "StandardCopyOption.ATOMIC_MOVE",
        '"stale_practice_revision"',
        "cloneObject(existingById[id]",
    )
    require(
        "app/src/main/java/com/dairr/android/security/CredentialStore.kt",
        "interface CredentialStore",
        "class DisabledCredentialStore",
        "UnsupportedOperationException",
    )
    dispatcher = (ROOT / "app/src/main/java/com/dairr/android/bridge/BridgeDispatcher.kt").read_text(encoding="utf-8")
    if "UnconfiguredBridgeDispatcher" in dispatcher:
        raise AssertionError("Android dispatcher still contains the unconfigured placeholder")
    print("Android production-edge validation passed.")


if __name__ == "__main__":
    main()
