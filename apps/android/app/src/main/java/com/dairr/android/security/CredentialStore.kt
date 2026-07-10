package com.dairr.android.security

/**
 * Boundary for provider tokens and API keys. A concrete implementation must
 * use Android Keystore-backed encryption; plaintext SharedPreferences is not
 * an acceptable replacement.
 */
interface CredentialStore {
    fun read(key: String): String?
    fun write(key: String, value: String)
    fun delete(key: String)
}

/**
 * Intentional fail-closed placeholder until the Android provider milestone.
 * This prevents the scaffold from accidentally storing a token in plaintext.
 */
class DisabledCredentialStore : CredentialStore {
    override fun read(key: String): String? = null

    override fun write(key: String, value: String) {
        throw UnsupportedOperationException("Secure Android credential storage is not configured.")
    }

    override fun delete(key: String) = Unit
}
