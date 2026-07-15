package com.dairr.android.bridge

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class BridgeContractTest {
    @Test
    fun `v2 request identity survives the Android envelope`() {
        val request = BridgeContract.requestFromEnvelope(
            JSONObject()
                .put("version", 2)
                .put("requestId", "request-42")
                .put("action", "createPastedPractice")
                .put("payload", JSONObject().put("sourceText", "private text"))
                .toString(),
        )
        assertNotNull(request)
        assertEquals("request-42", request!!.requestId)

        val event = BridgeEvent(request.requestId, "practiceSessionCreated").toJson()
        assertEquals("request-42", JSONObject(event).getString("requestId"))
        assertEquals(2, JSONObject(event).getInt("version"))
    }

    @Test
    fun `unknown actions and unsafe identifiers fail closed`() {
        assertNull(BridgeContract.requestFromEnvelope("""{"version":2,"requestId":"ok","action":"eraseEverything","payload":{}}"""))
        assertNull(BridgeContract.requestFromEnvelope("""{"version":2,"requestId":"bad id","action":"getCapabilities","payload":{}}"""))
        assertNull(BridgeContract.requestFromEnvelope("""{"version":99,"requestId":"ok","action":"getCapabilities","payload":{}}"""))
        assertNull(BridgeContract.requestFromEnvelope("""{"version":2,"requestId":"ok","action":"getCapabilities","payload":[]}"""))
    }
}
