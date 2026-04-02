package me.zwsmith.backend

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.get
import io.ktor.client.request.parameter
import io.ktor.http.HttpStatusCode
import io.ktor.server.application.Application
import io.ktor.server.response.respond
import io.ktor.server.routing.Routing
import io.ktor.server.routing.get
import io.ktor.server.routing.routing
import kotlinx.serialization.Serializable

private const val TMDB_BASE = "https://api.themoviedb.org/3"

// Internal TMDB response shapes — not exposed outside this file
@Serializable
private data class TmdbMovieSearchResponse(val results: List<TmdbMovie>)

@Serializable
private data class TmdbMovie(val id: Int, val title: String)

@Serializable
private data class TmdbPersonSearchResponse(val results: List<TmdbPerson>)

@Serializable
private data class TmdbPerson(val id: Int, val name: String)

@Serializable
private data class TmdbCreditsResponse(
  val id: Int,
  val cast: List<TmdbCastMember>
)

@Serializable
private data class TmdbCastMember(val id: Int)

fun Application.configureRoutes() {
  val client = buildTmdbClient()
  routing {
    moviesRoutes(client)
    peopleRoutes(client)
  }
}

private fun Routing.moviesRoutes(client: HttpClient) {
  get("/movies/search") {
    val query = call.request.queryParameters["query"]
      ?: return@get call.respond(HttpStatusCode.BadRequest, "query parameter required")
    val response: TmdbMovieSearchResponse = client.get("$TMDB_BASE/search/movie") {
      parameter("query", query)
      parameter("api_key", tmdbApiKey)
    }.body()
    call.respond(response.results.map { MovieSearchResult(it.id, it.title) })
  }
  get("/movies/{id}/credits") {
    val id = call.parameters["id"]?.toIntOrNull()
      ?: return@get call.respond(HttpStatusCode.BadRequest, "invalid movie id")
    val response: TmdbCreditsResponse = client.get("$TMDB_BASE/movie/$id/credits") {
      parameter("api_key", tmdbApiKey)
    }.body()
    call.respond(MovieCreditsResult(response.id, response.cast.map { it.id }))
  }
}

private fun Routing.peopleRoutes(client: HttpClient) {
  get("/people/search") {
    val query = call.request.queryParameters["query"]
      ?: return@get call.respond(HttpStatusCode.BadRequest, "query parameter required")
    val response: TmdbPersonSearchResponse = client.get("$TMDB_BASE/search/person") {
      parameter("query", query)
      parameter("api_key", tmdbApiKey)
    }.body()
    call.respond(response.results.map { PersonSearchResult(it.id, it.name) })
  }
}
