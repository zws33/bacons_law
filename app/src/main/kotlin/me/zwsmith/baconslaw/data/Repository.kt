package me.zwsmith.baconslaw.data

fun Repository(): Repository = RepositoryImpl(ApiClient.create())

interface Repository {
  suspend fun searchMovies(query: String): List<MovieSearchResult>
  suspend fun searchActors(query: String): List<PersonSearchResult>
  suspend fun fetchMovieCredits(movieId: Int): MovieCreditsResult
}

class RepositoryImpl(private val apiClient: ApiClient) : Repository {
  override suspend fun searchMovies(query: String): List<MovieSearchResult> =
    apiClient.searchMovies(query)

  override suspend fun searchActors(query: String): List<PersonSearchResult> =
    apiClient.searchActors(query)

  override suspend fun fetchMovieCredits(movieId: Int): MovieCreditsResult =
    apiClient.fetchCredits(movieId)
}
