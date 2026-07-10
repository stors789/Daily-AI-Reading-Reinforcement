package com.dairr.android.bridge

import org.json.JSONObject

/**
 * The mobile edge keeps the portable UI contract unchanged:
 *   window.__DAIRR_BRIDGE__.send(action, payload)
 *   window.DAIRR.receive({ event, payload })
 *
 * Only object payloads are accepted. Provider implementations own the action
 * semantics; this class only validates and transports the stable envelope.
 */
data class BridgeRequest(
    val action: String,
    val payload: JSONObject,
)

data class BridgeEvent(
    val event: String,
    val payload: JSONObject = JSONObject(),
) {
    fun toJson(): String = JSONObject()
        .put("event", event)
        .put("payload", payload)
        .toString()
}

object BridgeContract {
    const val JAVASCRIPT_INTERFACE = "AndroidDairrBridge"

    // This is an allow-list, not an Android implementation of these actions.
    // Keep it aligned with the portable web UI while the provider layer evolves.
    val supportedActions = setOf(
        "load",
        "selectSource",
        "selectDeck",
        "saveCollapsedDeckGroups",
        "saveFieldConfig",
        "generate",
        "debugPrompt",
        "listArticles",
        "loadArticle",
        "saveArticleCard",
        "saveApiSettings",
        "fetchModels",
        "saveDesktopSettings",
        "savePromptPreset",
        "deletePromptPreset",
        "selectPromptPreset",
        "saveUiLanguage",
    )

    fun requestOrNull(action: String, payloadJson: String): BridgeRequest? {
        if (action !in supportedActions) return null
        return runCatching { BridgeRequest(action, JSONObject(payloadJson)) }.getOrNull()
    }

    fun error(message: String): BridgeEvent = BridgeEvent(
        event = "error",
        payload = JSONObject().put("message", message),
    )
}
