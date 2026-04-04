package me.zwsmith.baconslaw.data

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.get
import io.ktor.client.request.parameter
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class MovieSearchResult(val id: Int, val title: String)
@Serializable
data class PersonSearchResult(val id: Int, val name: String)
@Serializable
data class MovieCreditsResult(val id: Int, val castIds: Set<Int>)
class DefaultApiClient : ApiClient {

  private val client = HttpClient(CIO) {
    install(ContentNegotiation) {
      json(Json { ignoreUnknownKeys = true })
    }
  }

 override suspend fun searchMovies(query: String): List<MovieSearchResult> {
    return client.get("$BASE_URL/movies/search") { parameter("query", query) }.body()
  }

  override suspend fun searchActors(query: String): List<PersonSearchResult> {
    return client.get("$BASE_URL/people/search") { parameter("query", query) }.body()
  }
  override suspend fun fetchCredits(movieId: Int): MovieCreditsResult {
    return client.get("$BASE_URL/movies/$movieId/credits").body()
  }
  companion object {
    const val BASE_URL = "https://bacons-law-backend-ic7p3y7rrq-uc.a.run.app"
  }
}

interface ApiClient {
  companion object {
    fun create(): ApiClient = DefaultApiClient()
  }

  suspend fun searchMovies(query: String): List<MovieSearchResult>
  suspend fun searchActors(query: String): List<PersonSearchResult>
  suspend fun fetchCredits(movieId: Int): MovieCreditsResult
}
