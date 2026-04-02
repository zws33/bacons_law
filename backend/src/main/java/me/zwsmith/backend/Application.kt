package me.zwsmith.backend

import io.ktor.serialization.kotlinx.json.json
import io.ktor.server.plugins.contentnegotiation.ContentNegotiation
import io.ktor.server.application.Application
import io.ktor.server.application.install
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty
import io.ktor.server.plugins.calllogging.CallLogging

fun main() {
  embeddedServer(Netty, port = 8080, module = Application::module).start(wait = true)
}

fun Application.module() {
  install(ContentNegotiation) { json() }
  install(CallLogging)
  configureRoutes()
}
