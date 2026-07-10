package com.dairr.android.bridge

/**
 * Android providers, local storage, and future AnkiDroid/export adapters plug
 * in here. The WebView never reaches provider APIs or credentials directly.
 */
fun interface BridgeDispatcher {
    fun dispatch(request: BridgeRequest, emit: (BridgeEvent) -> Unit)
}

/**
 * Safe development default. It deliberately persists nothing and performs no
 * network calls until a real Android provider adapter is installed.
 */
class UnconfiguredBridgeDispatcher : BridgeDispatcher {
    override fun dispatch(request: BridgeRequest, emit: (BridgeEvent) -> Unit) {
        emit(
            BridgeContract.error(
                "Android data providers are not configured yet; '${request.action}' is unavailable.",
            ),
        )
    }
}
