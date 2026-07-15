package com.dairr.android.bridge

import com.dairr.android.practice.AndroidPracticeRepository
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class AndroidBridgeDispatcherTest {
    @get:Rule
    val temporary = TemporaryFolder()

    @Test
    fun `capabilities are explicit and local practice is available`() {
        val dispatcher = AndroidBridgeDispatcher(AndroidPracticeRepository(temporary.newFolder()))
        val event = dispatch(dispatcher, request("getCapabilities"))
        val capabilities = event.payload.getJSONObject("capabilities")
        assertEquals("available", capabilities.getJSONObject("pasted_text_practice").getString("status"))
        assertEquals("data_absent", capabilities.getJSONObject("fsrs_values").getString("status"))
        assertEquals("provider_unsupported", capabilities.getJSONObject("provider_reasoning").getString("status"))
        dispatcher.close()
    }

    @Test
    fun `provider operation fails actionably without fake success or private text`() {
        val dispatcher = AndroidBridgeDispatcher(AndroidPracticeRepository(temporary.newFolder()))
        val request = request(
            "submitPracticeReview",
            JSONObject().put("translation", "a private diary translation"),
        )
        val event = dispatch(dispatcher, request)
        assertEquals("operationFailed", event.event)
        assertEquals("provider_unsupported", event.payload.getJSONObject("error").getString("code"))
        assertEquals("submitPracticeReview", event.payload.getString("action"))
        assertTrue(!event.toJson().contains("private diary"))
        dispatcher.close()
    }

    private fun request(action: String, payload: JSONObject = JSONObject()) =
        BridgeRequest(2, "request-test", action, payload)

    private fun dispatch(dispatcher: AndroidBridgeDispatcher, request: BridgeRequest): BridgeEvent {
        val latch = CountDownLatch(1)
        var result: BridgeEvent? = null
        dispatcher.dispatch(request) { event -> result = event; latch.countDown() }
        assertTrue(latch.await(3, TimeUnit.SECONDS))
        return result!!
    }
}
