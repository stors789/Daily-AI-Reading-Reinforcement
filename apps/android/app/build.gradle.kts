plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.dairr.android"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.dairr.android"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-dev"
    }

    val sharedWebDirectory = rootProject.file("../../addon/daily_ai_reading_reinforcement/web")
    val generatedWebAssets = layout.buildDirectory.dir("generated/assets/sharedWebUi")
    val prepareSharedWebUi by tasks.registering {
        group = "build setup"
        description = "Packages the portable DAIRR web UI with the Android bridge bootstrap."
        inputs.dir(sharedWebDirectory)
        outputs.dir(generatedWebAssets)

        doLast {
            val outputDirectory = generatedWebAssets.get().asFile.resolve("dairr")
            outputDirectory.mkdirs()

            val index = sharedWebDirectory.resolve("index.html").readText()
            val css = sharedWebDirectory.resolve("style.css").readText()
            val appJs = sharedWebDirectory.resolve("app.js").readText()
            val bridgeBootstrap = """
                <script>
                window.__DAIRR_BRIDGE__ = {
                  send: function(action, payload) {
                    window.AndroidDairrBridge.send(String(action), JSON.stringify(payload || {}));
                  }
                };
                </script>
            """.trimIndent()

            outputDirectory.resolve("index.html").writeText(
                """
                <!doctype html>
                <html lang="zh-CN">
                <head>
                  <meta charset="utf-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1">
                  <style>$css</style>
                </head>
                <body>
                $index
                $bridgeBootstrap
                <script>$appJs</script>
                </body>
                </html>
                """.trimIndent()
            )
        }
    }

    sourceSets {
        getByName("main").assets.srcDir(generatedWebAssets)
    }
    tasks.named("preBuild").configure {
        dependsOn(prepareSharedWebUi)
    }
}

dependencies {
    // Serves bundled assets from a secure HTTPS origin while keeping file access disabled.
    implementation("androidx.webkit:webkit:1.12.1")
}
