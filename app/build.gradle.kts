plugins {
    id("com.android.application")
    id("kotlin-android")
    id("kotlin-kapt")
}

android {
    compileSdk = libs.versions.compileSdk.get().toInt()

    defaultConfig {
        applicationId = "com.zwsmith.baconslaw"
        minSdk = libs.versions.minSdk.get().toInt()
        targetSdk = libs.versions.targetSdk.get().toInt()
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    val apiKey: String = project.findProperty("TMDB_API_KEY") as? String ?: ""
    buildTypes {
        debug {
            buildConfigField("String", "ApiKey", apiKey)
        }
        release {
            buildConfigField("String", "ApiKey", apiKey)
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    kotlinOptions {
        // work-runtime-ktx 2.1.0 and above now requires Java 8
        jvmTarget = "1.8"

    }
    kotlinOptions {
        jvmTarget = "1.8"
    }
    sourceSets {
        getByName("main").java.srcDirs("src/main/kotlin")
        getByName("androidTest").java.srcDirs("src/androidTest/kotlin")
        getByName("test").java.srcDirs("src/test/kotlin")
    }

    composeOptions {
        kotlinCompilerExtensionVersion = libs.versions.compose.compiler.get()
    }

    buildFeatures {
        compose = true
    }
    namespace = "com.zwsmith.bacons_law"
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.material)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.compose.runtime)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.gson)
    implementation(libs.retrofit2)
    implementation(libs.retrofit2.converter.gson)
    implementation(libs.okhttp3.logging.interceptor)
    implementation(libs.timber)
    implementation(libs.material)
    implementation(libs.androidx.compose.material)

    testImplementation(libs.kotest)
    testImplementation(libs.kotest.runner)
    testImplementation(libs.kotest.assertions)
    testImplementation(libs.kotlin.reflect)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}

tasks.withType(Test::class.java) {
    useJUnitPlatform()
    testLogging {
        events("passed", "skipped", "failed")
    }
}