plugins {
    alias(libs.plugins.kotlin.jvm)
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    testImplementation(libs.kotest)
    testImplementation(libs.kotest.runner)
    testImplementation(libs.kotest.assertions)
    testImplementation(libs.kotlin.reflect)
}

tasks.withType(Test::class.java) {
    useJUnitPlatform()
    testLogging {
        events("passed", "skipped", "failed")
    }
}
