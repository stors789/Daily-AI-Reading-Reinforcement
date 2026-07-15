package com.dairr.android

import android.app.Activity
import android.os.Bundle
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewAssetLoader
import com.dairr.android.bridge.BridgeContract
import com.dairr.android.bridge.AndroidBridgeDispatcher
import com.dairr.android.bridge.DairrJavascriptBridge
import com.dairr.android.practice.AndroidPracticeRepository
import java.io.ByteArrayInputStream
import java.io.File

class MainActivity : Activity() {
    private var webView: WebView? = null
    private var javascriptBridge: DairrJavascriptBridge? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val view = WebView(this)
        view.settings.apply {
            javaScriptEnabled = true // Required by the bundled DAIRR portable UI.
            // App-private DOM storage is used only as a crash-safe draft buffer.
            domStorageEnabled = true
            allowContentAccess = false
            allowFileAccess = false
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        }
        view.webViewClient = LocalOnlyWebViewClient(assetLoader)
        val bridge = DairrJavascriptBridge(
            view,
            AndroidBridgeDispatcher(AndroidPracticeRepository(File(filesDir, "practice_sessions"))),
        )
        view.addJavascriptInterface(
            bridge,
            BridgeContract.JAVASCRIPT_INTERFACE,
        )
        webView = view
        javascriptBridge = bridge
        setContentView(view)
        view.loadUrl(LOCAL_UI_URL)
    }

    override fun onDestroy() {
        javascriptBridge?.destroy()
        javascriptBridge = null
        webView?.apply {
            stopLoading()
            removeJavascriptInterface(BridgeContract.JAVASCRIPT_INTERFACE)
            webViewClient = WebViewClient()
            loadUrl("about:blank")
            removeAllViews()
            destroy()
        }
        webView = null
        super.onDestroy()
    }

    private class LocalOnlyWebViewClient(
        private val assetLoader: WebViewAssetLoader,
    ) : WebViewClient() {
        override fun shouldInterceptRequest(
            view: WebView,
            request: WebResourceRequest,
        ): WebResourceResponse? {
            val uri = request.url
            if (!isTrustedAsset(uri.scheme, uri.host, uri.path)) {
                // Block external subresources as well as top-level navigation.
                return WebResourceResponse(
                    "text/plain",
                    "UTF-8",
                    ByteArrayInputStream(ByteArray(0)),
                )
            }
            return assetLoader.shouldInterceptRequest(uri)
        }

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            // Do not let an external page gain access to AndroidDairrBridge.
            val uri = request.url
            return !isTrustedAsset(uri.scheme, uri.host, uri.path)
        }

        private fun isTrustedAsset(scheme: String?, host: String?, path: String?): Boolean {
            return scheme == "https" &&
                host == "appassets.androidplatform.net" &&
                path.orEmpty().startsWith("/assets/dairr/") &&
                !path.orEmpty().contains("..")
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
