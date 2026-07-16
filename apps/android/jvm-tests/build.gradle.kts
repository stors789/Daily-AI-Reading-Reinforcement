plugins {
    kotlin("jvm") version "2.0.21"
}

dependencies {
    implementation("org.json:json:20240303")
    testImplementation("junit:junit:4.13.2")
}

kotlin {
    jvmToolchain(17)
}

sourceSets {
    main {
        kotlin.setSrcDirs(listOf("../app/src/main/java"))
        kotlin.include(
            "com/dairr/android/bridge/BridgeContract.kt",
            "com/dairr/android/bridge/BridgeDispatcher.kt",
            "com/dairr/android/practice/AndroidPracticeRepository.kt",
        )
    }
    test {
        kotlin.setSrcDirs(listOf("../app/src/test/java"))
    }
}

tasks.test {
    useJUnit()
    reports.junitXml.required.set(true)
    testLogging {
        events("passed", "failed", "skipped")
    }
}
