package com.dairr.android.bridge

import android.webkit.JavascriptInterface
import android.webkit.WebView
import java.util.concurrent.atomic.AtomicBoolean

/** Exposes only the versioned DAIRR command envelope to the bundled UI. */
class DairrJavascriptBridge(
    private val webView: WebView,
    private val dispatcher: BridgeDispatcher,
) {
    private val destroyed = AtomicBoolean(false)

    @JavascriptInterface
    fun sendRequest(messageJson: String?) {
        val request = messageJson?.let(BridgeContract::requestFromEnvelope)
        if (request == null) {
            deliver(BridgeContract.invalidRequest())
            return
        }
        dispatcher.dispatch(request, ::deliver)
    }

    /** Compatibility entry point for older packaged UI assets. */
    @JavascriptInterface
    fun send(action: String?, payloadJson: String?) {
        val request = BridgeContract.legacyRequest(action.orEmpty(), payloadJson ?: "{}")
        if (request == null) {
            deliver(BridgeContract.invalidRequest())
            return
        }
        dispatcher.dispatch(request, ::deliver)
    }

    fun destroy() {
        if (destroyed.compareAndSet(false, true)) dispatcher.close()
    }

    private fun deliver(event: BridgeEvent) {
        if (destroyed.get()) return
        val envelope = event.toJson()
        webView.post {
            if (destroyed.get()) return@post
            // envelope is JSON produced by JSONObject, never interpolated raw text.
            webView.evaluateJavascript(
                "(function(e){if(window.DAIRR&&typeof window.DAIRR.receive==='function'){window.DAIRR.receive(e);}})($envelope);",
                null,
            )
        }
    }
}
