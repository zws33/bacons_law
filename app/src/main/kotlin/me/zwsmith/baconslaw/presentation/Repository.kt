package me.zwsmith.baconslaw.presentation

import me.zwsmith.baconslaw.data.ApiClient
import me.zwsmith.baconslaw.data.MovieCreditsResult
import me.zwsmith.baconslaw.data.MovieSearchResult
import me.zwsmith.baconslaw.data.PersonSearchResult
import timber.log.Timber

fun Repository(): Repository = RepositoryImpl(ApiClient.create())

interface Repository {

  suspend fun searchMovies(query: String): List<MovieSearchResult>
  suspend fun searchActors(query: String): List<PersonSearchResult>
  suspend fun fetchMovieCredits(movieId: Int): MovieCreditsResult?
}

class RepositoryImpl(private val apiClient: ApiClient) : Repository {

  override suspend fun searchMovies(query: String): List<MovieSearchResult> {
    return try {
      apiClient.searchMovies(query)
    } catch (e: Exception) {
      Timber.e(e)
      emptyList()
    }
  }

  override suspend fun searchActors(query: String): List<PersonSearchResult> {
    return try {
      apiClient.searchActors(query)
    } catch (e: Exception) {
      Timber.e(e)
      emptyList()
    }
  }

  override suspend fun fetchMovieCredits(movieId: Int): MovieCreditsResult? = try {
    apiClient.fetchCredits(movieId)
  } catch (e: Exception) {
    Timber.e(e)
    null
  }
}

