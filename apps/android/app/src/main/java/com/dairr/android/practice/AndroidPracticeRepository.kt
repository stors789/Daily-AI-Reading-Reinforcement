package com.dairr.android.practice

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.time.Instant
import java.util.UUID

class PracticeStoreException(
    val code: String,
    override val message: String,
    val retryable: Boolean = false,
) : Exception(message)

/**
 * App-private, versioned practice-session repository.
 *
 * Records are one JSON file per session. Updates start from the complete
 * existing document and replace only owned fields, so unknown envelope,
 * session, segment, and extension fields survive a round trip.
 */
class AndroidPracticeRepository(private val root: File) {
    companion object {
        const val SCHEMA_VERSION = 2
        const val MAX_SOURCE_CHARACTERS = 50_000
        const val MAX_SEGMENT_CHARACTERS = 20_000
        const val MAX_SEGMENTS = 500
        const val MAX_TRANSLATION_CHARACTERS = 100_000
        private val safeId = Regex("^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
    }

    init {
        if (!root.exists() && !root.mkdirs()) {
            throw IllegalStateException("Unable to initialize private practice storage.")
        }
        require(root.isDirectory) { "Practice storage must be a directory." }
    }

    @Synchronized
    fun createPasted(payload: JSONObject): StoredPractice {
        val sourceText = requiredText(payload, "sourceText", "Source text is required.")
            .replace("\r\n", "\n").replace('\r', '\n').trim()
        validateSourceLength(sourceText)
        val targetLanguage = requiredText(payload, "targetLanguage", "A target language is required.")
        val sourceLanguage = payload.optString("sourceLanguage", "auto").trim().ifEmpty { "auto" }
        val direction = payload.optString("direction", "source_to_target").trim()
        if (direction !in setOf("source_to_target", "target_to_source", "back_translation")) {
            throw PracticeStoreException("invalid_direction", "The selected translation direction is invalid.")
        }
        val segments = paragraphSegments(sourceText)
        val id = UUID.randomUUID().toString().replace("-", "")
        val now = Instant.now().toString()
        val session = JSONObject()
            .put("id", id)
            .put("kind", "pasted_text")
            .put("direction", direction)
            .put("sourceLanguage", sourceLanguage)
            .put("targetLanguage", targetLanguage)
            .put("sourceText", sourceText)
            .put("segments", segments)
            .put("createdAt", now)
            .put("updatedAt", now)
            .put("status", "draft")
            .put("proficiencyLevel", optionalText(payload, "proficiencyLevel") ?: JSONObject.NULL)
            .put("customReviewInstructions", payload.optString("customReviewInstructions", ""))
            .put("articleReference", JSONObject.NULL)
            .put("attempts", JSONArray())
            .put("segmentDrafts", JSONObject())
            .put("completeTextDraft", "")
            .put("lastAutosavedAt", JSONObject.NULL)
        return StoredPractice(document(session, revision = 0))
    }

    @Synchronized
    fun load(id: String): StoredPractice {
        val file = fileFor(id)
        if (!file.isFile) throw PracticeStoreException("practice_not_found", "The saved practice session was not found.")
        val document = try {
            JSONObject(file.readText(Charsets.UTF_8))
        } catch (_: Exception) {
            throw PracticeStoreException("practice_record_corrupt", "The saved practice session could not be opened.")
        }
        return validateDocument(document, expectedId = id)
    }

    @Synchronized
    fun save(record: StoredPractice) {
        val validated = validateDocument(record.document, record.id)
        writeAtomic(fileFor(validated.id), validated.document.toString())
    }

    @Synchronized
    fun list(): JSONArray {
        val summaries = mutableListOf<JSONObject>()
        root.listFiles { file -> file.isFile && file.name.endsWith(".json") }
            ?.forEach { file ->
                runCatching { load(file.name.removeSuffix(".json")) }.getOrNull()?.let { stored ->
                    val session = stored.session
                    summaries += JSONObject()
                        .put("id", stored.id)
                        .put("kind", session.optString("kind", "pasted_text"))
                        .put("sourceLanguage", session.optString("sourceLanguage", "auto"))
                        .put("targetLanguage", session.optString("targetLanguage", ""))
                        .put("status", session.optString("status", "draft"))
                        .put("updatedAt", session.optString("updatedAt", ""))
                        .put("attemptCount", session.optJSONArray("attempts")?.length() ?: 0)
                        .put("articleTitle", session.optJSONObject("articleReference")?.optString("title"))
                }
            }
        summaries.sortByDescending { it.optString("updatedAt") }
        return JSONArray(summaries)
    }

    @Synchronized
    fun delete(id: String): Boolean {
        val file = fileFor(id)
        return !file.exists() || file.delete()
    }

    @Synchronized
    fun saveDraft(record: StoredPractice, payload: JSONObject): StoredPractice {
        val working = StoredPractice(cloneObject(record.document))
        checkRevision(working, payload)
        val translation = payload.optString("translation", "")
        if (translation.length > MAX_TRANSLATION_CHARACTERS) {
            throw PracticeStoreException(
                "translation_too_long",
                "The translation exceeds the explicit $MAX_TRANSLATION_CHARACTERS character limit.",
            )
        }
        val session = working.session
        val segmentId = optionalText(payload, "segmentId")
        if (segmentId == null) {
            session.put("completeTextDraft", translation)
        } else {
            val known = segmentIds(session)
            if (segmentId !in known) throw PracticeStoreException("unknown_segment", "The selected segment no longer exists.")
            val drafts = session.optJSONObject("segmentDrafts") ?: JSONObject().also { session.put("segmentDrafts", it) }
            drafts.put(segmentId, translation)
        }
        return updated(working)
    }

    @Synchronized
    fun updateSegments(record: StoredPractice, payload: JSONObject): StoredPractice {
        val working = StoredPractice(cloneObject(record.document))
        checkRevision(working, payload)
        val incoming = payload.optJSONArray("segments")
            ?: throw PracticeStoreException("invalid_segments", "Practice segments must be an array.")
        if (incoming.length() !in 1..MAX_SEGMENTS) {
            throw PracticeStoreException("too_many_segments", "Use between 1 and $MAX_SEGMENTS practice segments.")
        }
        val session = working.session
        if ((session.optJSONArray("attempts")?.length() ?: 0) > 0) {
            throw PracticeStoreException("segmentation_locked", "Segmentation cannot change after review attempts exist.")
        }
        val existing = session.optJSONArray("segments") ?: JSONArray()
        val existingById = mutableMapOf<String, JSONObject>()
        for (index in 0 until existing.length()) {
            existing.optJSONObject(index)?.let { item -> existingById[item.optString("id")] = item }
        }
        val result = JSONArray()
        val ids = mutableSetOf<String>()
        val texts = mutableListOf<String>()
        for (index in 0 until incoming.length()) {
            val item = incoming.optJSONObject(index)
                ?: throw PracticeStoreException("invalid_segments", "Every practice segment must be an object.")
            val id = item.optString("id").trim()
            val text = item.optString("sourceText").trim()
            if (!safeId.matches(id) || !ids.add(id)) {
                throw PracticeStoreException("invalid_segment_id", "Practice segment identifiers must be unique and safe.")
            }
            if (text.isEmpty()) throw PracticeStoreException("empty_segment", "A practice segment cannot be empty.")
            if (text.length > MAX_SEGMENT_CHARACTERS) {
                throw PracticeStoreException("segment_too_long", "A segment exceeds the explicit $MAX_SEGMENT_CHARACTERS character limit.")
            }
            val merged = cloneObject(existingById[id] ?: JSONObject())
                .put("id", id)
                .put("position", index)
                .put("sourceText", text)
            if (item.has("referenceText")) merged.put("referenceText", item.opt("referenceText"))
            result.put(merged)
            texts += text
        }
        val joined = texts.joinToString("\n\n")
        validateSourceLength(joined)
        session.put("segments", result).put("sourceText", joined)
        // Drafts for removed segments must not be presented as active drafts.
        val oldDrafts = session.optJSONObject("segmentDrafts") ?: JSONObject()
        val retainedDrafts = JSONObject()
        ids.forEach { id -> if (oldDrafts.has(id)) retainedDrafts.put(id, oldDrafts.opt(id)) }
        session.put("segmentDrafts", retainedDrafts)
        return updated(working)
    }

    private fun updated(record: StoredPractice): StoredPractice {
        val now = Instant.now().toString()
        record.session.put("updatedAt", now).put("lastAutosavedAt", now)
        record.document.put("revision", record.revision + 1)
        return validateDocument(record.document, record.id)
    }

    private fun validateDocument(document: JSONObject, expectedId: String): StoredPractice {
        val version = when {
            document.has("schemaVersion") -> document.optInt("schemaVersion", -1)
            document.has("schema_version") -> document.optInt("schema_version", -1)
            else -> 0
        }
        if (version > SCHEMA_VERSION) {
            throw PracticeStoreException("unsupported_practice_schema", "This practice session was created by a newer DAIRR version.")
        }
        val session = document.optJSONObject("session")
            ?: if (version == 0) cloneObject(document) else null
            ?: throw PracticeStoreException("practice_record_corrupt", "The practice record has no session object.")
        val id = session.optString("id").trim()
        if (!safeId.matches(id) || id != expectedId) {
            throw PracticeStoreException("practice_record_corrupt", "The practice record identifier is invalid.")
        }
        requiredText(session, "sourceText", "The practice record has no source text.")
        requiredText(session, "targetLanguage", "The practice record has no target language.")
        val segments = session.optJSONArray("segments")
            ?: throw PracticeStoreException("practice_record_corrupt", "The practice record has no segments.")
        if (segments.length() !in 1..MAX_SEGMENTS) {
            throw PracticeStoreException("practice_record_corrupt", "The practice record has an invalid segment count.")
        }
        val normalized = if (version == 0) {
            JSONObject()
                .put("schemaVersion", SCHEMA_VERSION)
                .put("recordType", "dairr_practice_session")
                .put("revision", 0)
                .put("session", session)
        } else document
        return StoredPractice(normalized)
    }

    private fun checkRevision(record: StoredPractice, payload: JSONObject) {
        if (payload.has("revision") && payload.optInt("revision", Int.MIN_VALUE) != record.revision) {
            throw PracticeStoreException(
                "stale_practice_revision",
                "This practice session changed elsewhere. Reopen it before saving again.",
                retryable = true,
            )
        }
    }

    private fun paragraphSegments(source: String): JSONArray {
        val parts = source.split(Regex("\\n[\\t ]*\\n+"))
            .map(String::trim).filter(String::isNotEmpty)
        if (parts.size > MAX_SEGMENTS) {
            throw PracticeStoreException("too_many_segments", "The text contains more than $MAX_SEGMENTS segments. Split it into sessions.")
        }
        if (parts.any { it.length > MAX_SEGMENT_CHARACTERS }) {
            throw PracticeStoreException(
                "segment_too_long",
                "A paragraph exceeds $MAX_SEGMENT_CHARACTERS characters. Add a blank line to split it explicitly.",
            )
        }
        return JSONArray(parts.mapIndexed { index, text ->
            JSONObject()
                .put("id", UUID.randomUUID().toString().replace("-", ""))
                .put("position", index)
                .put("sourceText", text)
                .put("referenceText", JSONObject.NULL)
        })
    }

    private fun document(session: JSONObject, revision: Int): JSONObject = JSONObject()
        .put("schemaVersion", SCHEMA_VERSION)
        .put("recordType", "dairr_practice_session")
        .put("revision", revision)
        .put("session", session)

    private fun writeAtomic(target: File, value: String) {
        val temporary = File(root, ".${target.name}.${UUID.randomUUID()}.tmp")
        try {
            FileOutputStream(temporary).use { output ->
                output.write(value.toByteArray(Charsets.UTF_8))
                output.flush()
                output.fd.sync()
            }
            try {
                Files.move(
                    temporary.toPath(), target.toPath(),
                    StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING,
                )
            } catch (_: AtomicMoveNotSupportedException) {
                Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING)
            }
        } catch (_: Exception) {
            temporary.delete()
            throw PracticeStoreException("practice_save_failed", "The practice session could not be saved. Keep the workspace open and try again.", true)
        }
    }

    private fun fileFor(id: String): File {
        if (!safeId.matches(id)) throw PracticeStoreException("invalid_practice_id", "The practice session identifier is invalid.")
        return File(root, "$id.json")
    }

    private fun validateSourceLength(text: String) {
        if (text.length > MAX_SOURCE_CHARACTERS) {
            throw PracticeStoreException(
                "text_too_long",
                "The source text exceeds the explicit $MAX_SOURCE_CHARACTERS character limit and was not truncated.",
            )
        }
    }

    private fun segmentIds(session: JSONObject): Set<String> {
        val values = mutableSetOf<String>()
        val segments = session.optJSONArray("segments") ?: return values
        for (index in 0 until segments.length()) segments.optJSONObject(index)?.optString("id")?.let(values::add)
        return values
    }

    private fun requiredText(value: JSONObject, key: String, message: String): String {
        val text = value.optString(key).trim()
        if (text.isEmpty()) throw PracticeStoreException("invalid_practice_input", message)
        return text
    }

    private fun optionalText(value: JSONObject, key: String): String? =
        value.optString(key).trim().takeIf(String::isNotEmpty)

    private fun cloneObject(value: JSONObject): JSONObject = JSONObject(value.toString())
}

class StoredPractice(val document: JSONObject) {
    val session: JSONObject get() = document.getJSONObject("session")
    val id: String get() = session.getString("id")
    val revision: Int get() = document.optInt("revision", 0)

    fun sessionPayload(): JSONObject = JSONObject(session.toString()).put("revision", revision)
}
