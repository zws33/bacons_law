package me.zwsmith.backend

import io.ktor.serialization.kotlinx.json.json
import io.ktor.server.plugins.contentnegotiation.ContentNegotiation
import io.ktor.server.application.Application
import io.ktor.server.application.install
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty
import io.ktor.server.plugins.calllogging.CallLogging

fun main() {
  val port = System.getenv("PORT")?.toInt() ?: 8080
  embeddedServer(Netty, port = port, module = Application::module).start(wait = true)
}

fun Application.module() {
  install(ContentNegotiation) { json() }
  install(CallLogging)
  configureRoutes()
}
