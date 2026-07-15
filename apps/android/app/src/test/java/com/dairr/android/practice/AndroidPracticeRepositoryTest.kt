package com.dairr.android.practice

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class AndroidPracticeRepositoryTest {
    @get:Rule
    val temporary = TemporaryFolder()

    @Test
    fun `offline session round trip is atomic revisioned and unknown preserving`() {
        val repository = AndroidPracticeRepository(temporary.newFolder("sessions"))
        val created = repository.createPasted(
            JSONObject()
                .put("sourceText", "First paragraph.\n\nSecond paragraph.")
                .put("sourceLanguage", "English")
                .put("targetLanguage", "Japanese"),
        )
        created.document.put("futureEnvelopeField", JSONObject().put("enabled", true))
        created.session.put("futureSessionField", "keep-me")
        created.session.getJSONArray("segments").getJSONObject(0).put("futureSegmentField", 17)
        repository.save(created)

        val savedDraft = repository.saveDraft(
            repository.load(created.id),
            JSONObject()
                .put("revision", 0)
                .put("segmentId", created.session.getJSONArray("segments").getJSONObject(0).getString("id"))
                .put("translation", "下書き"),
        )
        repository.save(savedDraft)
        val loaded = repository.load(created.id)

        assertEquals(1, loaded.revision)
        assertTrue(loaded.document.getJSONObject("futureEnvelopeField").getBoolean("enabled"))
        assertEquals("keep-me", loaded.session.getString("futureSessionField"))
        assertEquals(17, loaded.session.getJSONArray("segments").getJSONObject(0).getInt("futureSegmentField"))
        assertEquals(1, repository.list().length())
        assertFalse(temporary.root.walkTopDown().any { it.name.endsWith(".tmp") })
    }

    @Test
    fun `manual segmentation validates limits order and stale revisions`() {
        val repository = AndroidPracticeRepository(temporary.newFolder("segments"))
        val created = repository.createPasted(
            JSONObject().put("sourceText", "One\n\nTwo").put("targetLanguage", "French"),
        )
        val original = created.session.getJSONArray("segments")
        val reordered = JSONArray()
            .put(JSONObject(original.getJSONObject(1).toString()))
            .put(JSONObject(original.getJSONObject(0).toString()).put("sourceText", "One edited"))
        val updated = repository.updateSegments(
            created,
            JSONObject().put("revision", 0).put("segments", reordered),
        )
        assertEquals(0, created.revision)
        assertEquals("One\n\nTwo", created.session.getString("sourceText"))
        assertEquals("Two\n\nOne edited", updated.session.getString("sourceText"))
        assertEquals(0, updated.session.getJSONArray("segments").getJSONObject(0).getInt("position"))

        val stale = runCatching {
            repository.saveDraft(updated, JSONObject().put("revision", 0).put("translation", "stale"))
        }.exceptionOrNull() as PracticeStoreException
        assertEquals("stale_practice_revision", stale.code)
        assertTrue(stale.retryable)
    }

    @Test
    fun `oversize input is rejected without truncation or a record`() {
        val repository = AndroidPracticeRepository(temporary.newFolder("limits"))
        val error = runCatching {
            repository.createPasted(
                JSONObject()
                    .put("sourceText", "x".repeat(AndroidPracticeRepository.MAX_SOURCE_CHARACTERS + 1))
                    .put("targetLanguage", "French"),
            )
        }.exceptionOrNull() as PracticeStoreException
        assertEquals("text_too_long", error.code)
        assertEquals(0, repository.list().length())
    }
}
