package com.dairr.android.bridge

import org.json.JSONObject
import java.util.UUID

data class BridgeRequest(
    val version: Int,
    val requestId: String,
    val action: String,
    val payload: JSONObject,
)

data class BridgeEvent(
    val requestId: String,
    val event: String,
    val payload: JSONObject = JSONObject(),
    val operationId: String? = null,
) {
    fun toJson(): String = JSONObject()
        .put("version", BridgeContract.VERSION)
        .put("requestId", requestId)
        .put("event", event)
        .put("payload", payload)
        .also { envelope -> operationId?.let { envelope.put("operationId", it) } }
        .toString()
}

/**
 * Versioned, allow-listed transport shared with the portable web UI.
 * Compatibility surface: window.__DAIRR_BRIDGE__.send(action, payload)
 * Delivery surface: window.DAIRR.receive({ event, payload })
 * The production bootstrap additionally preserves v2 requestId envelopes.
 */
object BridgeContract {
    const val VERSION = 2
    const val JAVASCRIPT_INTERFACE = "AndroidDairrBridge"
    const val MAX_MESSAGE_CHARACTERS = 600_000
    private const val MAX_REQUEST_ID_CHARACTERS = 128
    private const val MAX_ACTION_CHARACTERS = 96
    private val safeId = Regex("^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

    val localActions = setOf(
        "getCapabilities",
        "createPastedPractice",
        "listPracticeSessions",
        "loadPracticeSession",
        "savePracticeDraft",
        "updatePracticeSegments",
        "deletePracticeSession",
    )

    val controlActions = setOf("operationStatus", "cancelOperation")

    // These are deliberately recognized so Android can return a specific,
    // actionable capability result instead of an ambiguous unknown action.
    val unsupportedActions = setOf(
        "createArticlePractice",
        "submitPracticeReview",
        "getScoringConfig",
        "saveScoringConfig",
        "resetScoringConfig",
        "importScoringConfig",
        "exportScoringConfig",
        "previewScoring",
        "listPromptTemplates",
        "getPromptTemplate",
        "savePromptTemplate",
        "resetPromptTemplate",
        "importPromptTemplates",
        "exportPromptTemplates",
        "previewPrompt",
        "getReasoningSettings",
        "saveReasoningSettings",
        "previewReasoningSettings",
        "generateTargetAware",
        "loadStudySignals",
        // Legacy portable-UI actions remain fail closed on Android.
        "load", "selectSource", "selectDeck", "saveCollapsedDeckGroups",
        "saveFieldConfig", "generate", "debugPrompt", "listArticles",
        "loadArticle", "saveArticleCard", "saveApiSettings", "fetchModels",
        "saveDesktopSettings", "savePromptPreset", "deletePromptPreset",
        "selectPromptPreset", "saveUiLanguage",
    )

    val supportedActions = localActions + controlActions + unsupportedActions

    fun requestFromEnvelope(messageJson: String): BridgeRequest? {
        if (messageJson.length > MAX_MESSAGE_CHARACTERS) return null
        return runCatching {
            val message = JSONObject(messageJson)
            val version = message.optInt("version", VERSION)
            val action = message.optString("action").trim()
            val requestId = message.optString("requestId").trim().ifEmpty { UUID.randomUUID().toString() }
            val rawPayload = message.opt("payload")
            require(rawPayload == null || rawPayload === JSONObject.NULL || rawPayload is JSONObject)
            val payload = rawPayload as? JSONObject ?: JSONObject()
            require(version == 1 || version == VERSION)
            require(action.length in 1..MAX_ACTION_CHARACTERS && action in supportedActions)
            require(requestId.length <= MAX_REQUEST_ID_CHARACTERS && safeId.matches(requestId))
            BridgeRequest(version, requestId, action, payload)
        }.getOrNull()
    }

    fun legacyRequest(action: String, payloadJson: String): BridgeRequest? {
        val requestId = UUID.randomUUID().toString()
        return requestFromEnvelope(
            JSONObject()
                .put("version", VERSION)
                .put("requestId", requestId)
                .put("action", action)
                .put("payload", runCatching { JSONObject(payloadJson) }.getOrNull() ?: return null)
                .toString(),
        )
    }

    fun failure(
        request: BridgeRequest,
        code: String,
        message: String,
        retryable: Boolean = false,
        operationId: String? = null,
    ): BridgeEvent = BridgeEvent(
        requestId = request.requestId,
        event = "operationFailed",
        payload = JSONObject()
            .put("status", "failed")
            .put("action", request.action)
            .put(
                "error",
                JSONObject()
                    .put("code", code)
                    .put("message", message)
                    .put("retryable", retryable),
            ),
        operationId = operationId,
    )

    fun invalidRequest(requestId: String = UUID.randomUUID().toString()): BridgeEvent = BridgeEvent(
        requestId = requestId,
        event = "operationFailed",
        payload = JSONObject()
            .put("status", "failed")
            .put(
                "error",
                JSONObject()
                    .put("code", "invalid_bridge_request")
                    .put("message", "The Android bridge request was invalid or unsupported.")
                    .put("retryable", false),
            ),
    )
}
