plugins {
  alias(libs.plugins.android.application)
  alias(libs.plugins.kotlin.compose)
  alias(libs.plugins.kotlin.serialization)
}

android {
  namespace = "me.zwsmith.baconslaw"
  compileSdk = libs.versions.compileSdk.get().toInt()

  defaultConfig {
    applicationId = "me.zwsmith.baconslaw"
    minSdk = libs.versions.minSdk.get().toInt()
    targetSdk = libs.versions.targetSdk.get().toInt()
    versionCode = 1
    versionName = "1.0"
    testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
  }
  buildTypes {
    debug {
      buildConfigField("String", "BACKEND_URL", "\"http://10.0.2.2:8080\"")
    }
    release {
      isMinifyEnabled = true
      isShrinkResources = true
      proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
      buildConfigField("String", "BACKEND_URL", "\"https://bacons-law-backend-ic7p3y7rrq-uc.a.run.app\"")
    }
  }

  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
  }

  buildFeatures {
    compose = true
    buildConfig = true
  }
}

dependencies {
  implementation(platform(libs.androidx.compose.bom))
  implementation(libs.bundles.compose)
  implementation(libs.bundles.lifecycle)
  implementation(libs.bundles.ktor.client)
  implementation(libs.androidx.core.ktx)
  implementation(libs.androidx.appcompat)
  implementation(libs.androidx.navigation.compose)
  implementation(libs.material.icons.extended)
  implementation(libs.material)
  implementation(libs.timber)
  implementation(libs.coil.compose)
  implementation(libs.androidx.compose.ui.tooling.preview)
  debugImplementation(libs.androidx.compose.ui.tooling)
  implementation(project(":core"))

  testImplementation(libs.bundles.test.bundle)
  androidTestImplementation(libs.androidx.test.ext.junit)
  androidTestImplementation(libs.androidx.espresso.core)
}

tasks.withType(Test::class.java) {
  useJUnitPlatform()
  testLogging {
    events("passed", "skipped", "failed")
  }
}
