import java.util.Properties

plugins {
  alias(libs.plugins.kotlin.jvm)
  alias(libs.plugins.kotlin.serialization)
  application
}

kotlin {
  jvmToolchain(17)
}

application {
  mainClass.set("me.zwsmith.backend.ApplicationKt")
}

val localProperties = Properties().apply {
  val file = rootProject.file("local.properties")
  if (file.exists()) load(file.inputStream())
}

tasks.withType<JavaExec> {
  val key = localProperties.getProperty("TMDB_API_KEY")
    ?: System.getenv("TMDB_API_KEY")
  if (key != null) environment("TMDB_API_KEY", key)
}

tasks.withType<Test> {
  useJUnitPlatform()
}

dependencies {
  implementation(project(":core"))
  implementation(libs.bundles.ktor.server)
  implementation(libs.bundles.ktor.client)
  testImplementation(libs.bundles.test.bundle)
}
