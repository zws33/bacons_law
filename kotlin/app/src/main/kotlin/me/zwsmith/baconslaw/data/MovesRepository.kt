package me.zwsmith.baconslaw.data

import me.zwsmith.core.Move

fun MovesRepository(): MovesRepository = MovesRepositoryImpl(ApiClient.create())
interface MovesRepository {
  suspend fun search(query: String, moveType: MoveType): List<MoveCandidate>
  suspend fun getMove(candidate: MoveCandidate): Move
}

class MovesRepositoryImpl(private val apiClient: ApiClient) : MovesRepository {
  override suspend fun search(
    query: String,
    moveType: MoveType
  ): List<MoveCandidate> {
    return when (moveType) {
      MoveType.ACTOR -> {
        apiClient.searchActors(query).map {
          MoveCandidate.Actor(it.id, it.name, TMDB_IMAGE_BASE_URL+ it.profilePath)
        }
      }
      MoveType.MOVIE -> {
        apiClient.searchMovies(query).map {
          MoveCandidate.Movie(it.id, it.title, it.releaseYear)
        }
      }
    }
  }

  override suspend fun getMove(candidate: MoveCandidate): Move {
    return when(candidate) {
      is MoveCandidate.Actor ->  Move.Actor(candidate.id, candidate.displayText, candidate.imageUrl)
      is MoveCandidate.Movie ->  {
        val castIds = apiClient.fetchCredits(candidate.id).castIds
        Move.Movie(candidate.id, candidate.displayText, castIds)
      }
    }
  }

  companion object {
    const val TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w185"
  }
}

enum class MoveType {
  ACTOR,
  MOVIE
}

sealed class MoveCandidate {
  abstract val id: Int
  abstract val displayText: String

  data class Actor(
    override val id: Int,
    override val displayText: String,
    val imageUrl: String?,
  ) : MoveCandidate()

  data class Movie(
    override val id: Int,
    override val displayText: String,
    val releaseYear: String?,
  ) : MoveCandidate()
}
