package com.dairr.android.bridge

import com.dairr.android.practice.AndroidPracticeRepository
import com.dairr.android.practice.PracticeStoreException
import com.dairr.android.practice.StoredPractice
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.atomic.AtomicBoolean

interface BridgeDispatcher : AutoCloseable {
    fun dispatch(request: BridgeRequest, emit: (BridgeEvent) -> Unit)
    override fun close() = Unit
}

/**
 * Production Android edge for offline pasted-text practice.
 *
 * It intentionally does not embed or duplicate Python scoring/provider logic.
 * Android provider, Anki, article, scoring, prompt, and reasoning operations
 * return explicit capability failures until supported adapters are installed.
 */
class AndroidBridgeDispatcher(
    private val repository: AndroidPracticeRepository,
    private val executor: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "dairr-android-bridge").apply { isDaemon = true }
    },
) : BridgeDispatcher {
    private val closed = AtomicBoolean(false)
    private val workingSessions = ConcurrentHashMap<String, StoredPractice>()

    override fun dispatch(request: BridgeRequest, emit: (BridgeEvent) -> Unit) {
        if (closed.get()) return
        try {
            executor.execute {
                if (closed.get()) return@execute
                val event = try {
                    handle(request)
                } catch (error: PracticeStoreException) {
                    BridgeContract.failure(request, error.code, error.message, error.retryable)
                } catch (_: Exception) {
                    // Never return exception strings: they may contain paths or private text.
                    BridgeContract.failure(
                        request,
                        "android_operation_failed",
                        "The Android operation failed. Keep this workspace open and try again.",
                        retryable = true,
                    )
                }
                if (!closed.get()) emit(event)
            }
        } catch (_: RejectedExecutionException) {
            if (!closed.get()) {
                emit(BridgeContract.failure(request, "android_bridge_unavailable", "The Android workspace is closing."))
            }
        }
    }

    override fun close() {
        if (closed.compareAndSet(false, true)) {
            workingSessions.clear()
            executor.shutdownNow()
        }
    }

    private fun handle(request: BridgeRequest): BridgeEvent = when (request.action) {
        "getCapabilities" -> event(request, "capabilitiesLoaded", capabilitySnapshot())
        "createPastedPractice" -> createPasted(request)
        "listPracticeSessions" -> event(
            request,
            "practiceSessionsLoaded",
            JSONObject().put("sessions", repository.list()),
        )
        "loadPracticeSession" -> {
            val record = load(requiredId(request.payload))
            event(request, "practiceSessionLoaded", JSONObject().put("session", record.sessionPayload()))
        }
        "savePracticeDraft" -> saveDraft(request)
        "updatePracticeSegments" -> updateSegments(request)
        "deletePracticeSession" -> delete(request)
        "operationStatus", "cancelOperation" -> BridgeContract.failure(
            request,
            "cancellation_unavailable",
            "No cancellable Android provider operation is active. Local practice saves finish in the background.",
        )
        else -> unsupported(request)
    }

    private fun createPasted(request: BridgeRequest): BridgeEvent {
        val record = repository.createPasted(request.payload)
        val save = request.payload.optBoolean("save", false)
        if (save) repository.save(record)
        workingSessions[record.id] = record
        return event(
            request,
            "practiceSessionCreated",
            JSONObject().put("session", record.sessionPayload()).put("saved", save),
        )
    }

    private fun saveDraft(request: BridgeRequest): BridgeEvent {
        val id = requiredId(request.payload)
        val updated = repository.saveDraft(load(id), request.payload)
        val persist = request.payload.optBoolean("persist", true)
        if (persist) repository.save(updated)
        workingSessions[id] = updated
        return event(
            request,
            "practiceDraftSaved",
            JSONObject().put("session", updated.sessionPayload()).put("persisted", persist),
        )
    }

    private fun updateSegments(request: BridgeRequest): BridgeEvent {
        val id = requiredId(request.payload)
        val updated = repository.updateSegments(load(id), request.payload)
        if (request.payload.optBoolean("persist", true)) repository.save(updated)
        workingSessions[id] = updated
        return event(
            request,
            "practiceSegmentsUpdated",
            JSONObject().put("session", updated.sessionPayload()),
        )
    }

    private fun delete(request: BridgeRequest): BridgeEvent {
        val id = requiredId(request.payload)
        workingSessions.remove(id)
        if (!repository.delete(id)) {
            throw PracticeStoreException("practice_delete_failed", "The practice session could not be deleted.", true)
        }
        return event(request, "practiceSessionDeleted", JSONObject().put("sessionId", id))
    }

    private fun load(id: String): StoredPractice = workingSessions[id] ?: repository.load(id).also {
        workingSessions[id] = it
    }

    private fun unsupported(request: BridgeRequest): BridgeEvent {
        val (code, message) = when (request.action) {
            "createArticlePractice", "listArticles", "loadArticle" ->
                "article_history_unavailable" to "Saved DAIRR article history is not available in the Android shell yet. Use pasted-text practice instead."
            "submitPracticeReview", "generateTargetAware", "generate", "fetchModels" ->
                "provider_unsupported" to "No Android AI provider is configured. Your local practice draft remains available; review it on desktop or in the add-on."
            "loadStudySignals", "previewScoring", "getScoringConfig", "saveScoringConfig",
            "resetScoringConfig", "importScoringConfig", "exportScoringConfig",
            "selectSource", "selectDeck", "saveArticleCard" ->
                "anki_data_absent" to "Android has no supported Anki data adapter in this release. Offline pasted-text practice remains available."
            "listPromptTemplates", "getPromptTemplate", "savePromptTemplate", "resetPromptTemplate",
            "importPromptTemplates", "exportPromptTemplates", "previewPrompt" ->
                "provider_unsupported" to "Prompt customization requires an AI provider adapter, which Android does not support yet."
            "getReasoningSettings", "saveReasoningSettings", "previewReasoningSettings" ->
                "provider_unsupported" to "Reasoning controls are unavailable because Android has no configured AI provider."
            else -> "unavailable_in_android" to "This operation is not available in the Android shell. Offline pasted-text practice remains available."
        }
        return BridgeContract.failure(request, code, message)
    }

    private fun requiredId(payload: JSONObject): String {
        val value = payload.optString("sessionId").trim()
        if (value.isEmpty()) throw PracticeStoreException("missing_identifier", "A practice session identifier is required.")
        return value
    }

    private fun event(request: BridgeRequest, name: String, payload: JSONObject): BridgeEvent =
        BridgeEvent(request.requestId, name, payload)

    private fun capabilitySnapshot(): JSONObject {
        val capabilities = JSONObject()
            .put("pasted_text_practice", capability("pasted_text_practice", "available", "none", "local_history", "Private offline practice storage is ready."))
            .put("article_history", capability("article_history", "data_absent", "missing_field", "unknown", "Android article history is not configured; paste article text to practise it."))
            .put("anki_connection", capability("anki_connection", "unavailable_in_mode", "host_mode_limitation", "unknown", "No supported Android Anki adapter is installed."))
            .put("internal_anki_apis", capability("internal_anki_apis", "unavailable_in_mode", "host_mode_limitation", "unknown", "Anki desktop internals are never exposed to Android."))
            .put("review_history", capability("review_history", "data_absent", "missing_field", "unknown", "No normalized Android review-history source is configured."))
            .put("fsrs_values", capability("fsrs_values", "data_absent", "fsrs_not_available", "unknown", "FSRS scheduling values are absent on Android."))
            .put("target_card_scoring", capability("target_card_scoring", "data_absent", "missing_field", "unknown", "Scoring is unavailable without normalized Anki review data."))
            .put("custom_prompts", capability("custom_prompts", "provider_unsupported", "provider_limitation", "unknown", "Android has no AI provider adapter in this release."))
            .put("provider_reasoning", capability("provider_reasoning", "provider_unsupported", "provider_limitation", "unknown", "Reasoning controls require a supported Android provider adapter."))
            .put("cancellation", capability("cancellation", "provider_unsupported", "provider_limitation", "unknown", "There are no Android provider operations to cancel; local I/O is lifecycle-cancelled."))
        return JSONObject()
            .put("capabilities", capabilities)
            .put(
                "practiceLimits",
                JSONObject()
                    .put("maxSourceCharacters", AndroidPracticeRepository.MAX_SOURCE_CHARACTERS)
                    .put("maxSegmentCharacters", AndroidPracticeRepository.MAX_SEGMENT_CHARACTERS)
                    .put("maxSegments", AndroidPracticeRepository.MAX_SEGMENTS)
                    .put("maxTranslationCharacters", AndroidPracticeRepository.MAX_TRANSLATION_CHARACTERS),
            )
    }

    private fun capability(id: String, status: String, reason: String, provenance: String, detail: String): JSONObject =
        JSONObject()
            .put("id", id)
            .put("status", status)
            .put("reason", reason)
            .put("provenance", provenance)
            .put("detail", detail)
}
