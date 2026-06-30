plugins {
    alias(libs.plugins.kotlin.multiplatform)
}

kotlin {
    jvm()
    iosX64()
    iosArm64()
    iosSimulatorArm64()

    jvmToolchain(17)

    sourceSets {
        commonMain {
            dependencies {
                // No dependencies for now
            }
        }
        val jvmTest by getting {
            dependencies {
                implementation(libs.bundles.test.bundle)
            }
        }
    }
}

tasks.withType(Test::class.java) {
    useJUnitPlatform()
    testLogging {
        events("passed", "skipped", "failed")
    }
}
