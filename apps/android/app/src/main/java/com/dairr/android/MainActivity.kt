package com.dairr.android

import android.app.Activity
import android.os.Bundle
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewAssetLoader
import com.dairr.android.bridge.BridgeContract
import com.dairr.android.bridge.DairrJavascriptBridge
import com.dairr.android.bridge.UnconfiguredBridgeDispatcher

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val webView = WebView(this)
        webView.settings.apply {
            javaScriptEnabled = true // Required by the bundled DAIRR portable UI.
            domStorageEnabled = false
            allowContentAccess = false
            allowFileAccess = false
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        }
        webView.webViewClient = LocalOnlyWebViewClient(assetLoader)
        webView.addJavascriptInterface(
            DairrJavascriptBridge(webView, UnconfiguredBridgeDispatcher()),
            BridgeContract.JAVASCRIPT_INTERFACE,
        )
        setContentView(webView)
        webView.loadUrl(LOCAL_UI_URL)
    }

    private class LocalOnlyWebViewClient(
        private val assetLoader: WebViewAssetLoader,
    ) : WebViewClient() {
        override fun shouldInterceptRequest(
            view: WebView,
            request: WebResourceRequest,
        ): WebResourceResponse? = assetLoader.shouldInterceptRequest(request.url)

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            // Do not let an external page gain access to AndroidDairrBridge.
            return !request.url.toString().startsWith(LOCAL_UI_URL)
        }
    }

    private companion object {
        const val LOCAL_UI_URL = "https://appassets.androidplatform.net/assets/dairr/index.html"
    }

    private val assetLoader by lazy {
        WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()
    }
}
