package me.zwsmith.baconslaw.data

import com.google.common.truth.Truth.assertThat
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import me.zwsmith.core.Move
import org.junit.jupiter.api.Test

class MovesRepositoryTest {
  private val apiClient = mockk<ApiClient>()
  private val repository = MovesRepositoryImpl(apiClient)

  @Test
  fun `search actors returns mapped candidates`() = runTest {
    val searchResults = listOf(
      PersonSearchResult(id = 1, name = "Tom Hanks", profilePath = "/hanks.jpg")
    )
    coEvery { apiClient.searchActors("Tom") } returns searchResults

    val results = repository.search("Tom", MoveType.ACTOR)

    val expected = listOf(
      MoveCandidate.Actor(id = 1, displayText = "Tom Hanks", imageUrl = "/hanks.jpg")
    )
    assertThat(results).isEqualTo(expected)
  }

  @Test
  fun `search movies returns mapped candidates`() = runTest {
    val searchResults = listOf(
      MovieSearchResult(id = 10, title = "Cast Away", releaseYear = "2000", posterPath = "/castaway.jpg")
    )
    coEvery { apiClient.searchMovies("Cast") } returns searchResults

    val results = repository.search("Cast", MoveType.MOVIE)

    val expected = listOf(
      MoveCandidate.Movie(id = 10, displayText = "Cast Away", releaseYear = "2000")
    )
    assertThat(results).isEqualTo(expected)
  }

  @Test
  fun `getMove for actor candidate returns Actor move`() = runTest {
    val candidate = MoveCandidate.Actor(id = 1, displayText = "Tom Hanks", imageUrl = "/hanks.jpg")

    val result = repository.getMove(candidate)

    val expected = Move.Actor(id = 1, displayText = "Tom Hanks", imagePath = "/hanks.jpg")
    assertThat(result).isEqualTo(expected)
  }

  @Test
  fun `getMove for movie candidate fetches credits and returns Movie move`() = runTest {
    val candidate = MoveCandidate.Movie(id = 10, displayText = "Cast Away", releaseYear = "2000")
    val credits = MovieCreditsResult(id = 10, castIds = setOf(1, 2, 3))
    coEvery { apiClient.fetchCredits(10) } returns credits

    val result = repository.getMove(candidate)

    val expected = Move.Movie(id = 10, displayText = "Cast Away", castIds = setOf(1, 2, 3))
    assertThat(result).isEqualTo(expected)
  }
}
