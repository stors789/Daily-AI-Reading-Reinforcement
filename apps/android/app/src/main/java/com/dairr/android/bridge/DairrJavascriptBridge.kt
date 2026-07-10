package com.dairr.android.bridge

import android.webkit.JavascriptInterface
import android.webkit.WebView

/** Exposes only the small DAIRR command envelope to the bundled, trusted UI. */
class DairrJavascriptBridge(
    private val webView: WebView,
    private val dispatcher: BridgeDispatcher,
) {
    @JavascriptInterface
    fun send(action: String?, payloadJson: String?) {
        val request = BridgeContract.requestOrNull(action.orEmpty(), payloadJson ?: "{}")
        if (request == null) {
            deliver(BridgeContract.error("Invalid DAIRR bridge request."))
            return
        }
        dispatcher.dispatch(request, ::deliver)
    }

    private fun deliver(event: BridgeEvent) {
        val envelope = event.toJson()
        webView.post {
            // envelope is JSON produced by JSONObject; it is not interpolated user script.
            webView.evaluateJavascript(
                "(function(e) { if (window.DAIRR && typeof window.DAIRR.receive === 'function') { window.DAIRR.receive(e); } })($envelope);",
                null,
            )
        }
    }
}
