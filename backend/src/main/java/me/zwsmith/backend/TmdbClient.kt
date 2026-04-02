package me.zwsmith.backend

import io.ktor.client.HttpClient
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

val tmdbApiKey get() = System.getenv("TMDB_API_KEY") ?: error("TMDB_API_KEY not set")

fun buildTmdbClient() = HttpClient(CIO) {
  install(ContentNegotiation) {
    json(Json { ignoreUnknownKeys = true })
  }
}
