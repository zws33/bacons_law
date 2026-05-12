package me.zwsmith.baconslaw.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.zwsmith.baconslaw.data.MoveCandidate
import me.zwsmith.baconslaw.ui.GameplayViewModel
import me.zwsmith.baconslaw.ui.SearchState
import me.zwsmith.baconslaw.ui.UiState
import me.zwsmith.baconslaw.ui.components.ChainDisplay
import me.zwsmith.baconslaw.ui.components.ErrorMessage
import me.zwsmith.baconslaw.ui.components.MoveCandidates
import me.zwsmith.baconslaw.ui.components.SearchBox
import me.zwsmith.baconslaw.ui.components.TmdbAttribution
import me.zwsmith.baconslaw.ui.theme.BaconsLawTheme
import me.zwsmith.core.Move

@Composable
internal fun GamePlayScreen(
  modifier: Modifier = Modifier,
  viewModel: GameplayViewModel,
  onGameOver: (String) -> Unit = {},
) {
  val uiState by viewModel.uiState.collectAsStateWithLifecycle()
  val focusRequester = remember { FocusRequester() }

  LaunchedEffect(Unit) {
    viewModel.gameOverEvent.collect { winnerName ->
      onGameOver(winnerName)
    }
  }

  GamePlayScreenContent(
    uiState = uiState,
    query = viewModel.query,
    onTextInput = viewModel::onTextInput,
    onResultSelected = viewModel::onResultSelected,
    onForfeit = viewModel::forfeit,
    onDismissError = viewModel::onDismissError,
    modifier = modifier,
    focusRequester = focusRequester,
  )
}

@Composable
internal fun GamePlayScreenContent(
  uiState: UiState,
  query: String,
  onTextInput: (String) -> Unit,
  onResultSelected: (MoveCandidate) -> Unit,
  onForfeit: () -> Unit,
  onDismissError: () -> Unit,
  modifier: Modifier = Modifier,
  focusRequester: FocusRequester? = null,
) {
  Box(modifier = modifier.fillMaxSize()) {
    ChainDisplay(
      moves = uiState.movesChain,
      modifier = Modifier.fillMaxSize(),
      contentPadding = PaddingValues(
        start = 16.dp,
        end = 16.dp,
        top = 16.dp,
        bottom = 180.dp,
      ),
    )

    Column(
      modifier = Modifier
        .align(Alignment.BottomCenter)
        .fillMaxWidth()
        .background(MaterialTheme.colorScheme.background)
        .padding(horizontal = 16.dp, vertical = 8.dp),
      verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
      when (val state = uiState.searchState) {
        is SearchState.Idle -> {
          if (state.results.isNotEmpty()) {
            MoveCandidates(
              results = state.results.take(3),
              onResultClicked = onResultSelected,
            )
          }
        }
        SearchState.Searching -> {
          Text(
            text = "Searching…",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            modifier = Modifier.padding(horizontal = 4.dp),
          )
        }
        is SearchState.Error -> {
          ErrorMessage(
            message = state.message,
            onDismiss = onDismissError,
          )
        }
      }

      SearchBox(
        text = query,
        onTextInput = onTextInput,
        focusRequester = focusRequester,
      )

      TextButton(
        onClick = onForfeit,
        modifier = Modifier.fillMaxWidth()
      ) {
        Text("I can't answer")
      }

      TmdbAttribution()
    }
  }
}

// region Previews

private val previewChain = listOf(
  Move.Actor(id = 1, displayText = "Kevin Bacon"),
  Move.Movie(id = 10, displayText = "A Few Good Men", castIds = setOf(1, 2), releaseYear = "1992"),
  Move.Actor(id = 2, displayText = "Tom Hanks"),
)

private val previewMovieResults = listOf(
  MoveCandidate.Movie(id = 20, displayText = "Cast Away", releaseYear = "2000"),
  MoveCandidate.Movie(id = 30, displayText = "Forrest Gump", releaseYear = "1994"),
  MoveCandidate.Movie(id = 40, displayText = "The Terminal", releaseYear = "2004"),
)

@Preview(showBackground = true, name = "Chain + results")
@Composable
private fun GamePlayScreenWithResultsPreview() {
  BaconsLawTheme {
    GamePlayScreenContent(
      uiState = UiState(
        currentPlayerDisplayText = "Bob",
        movesChain = previewChain,
        searchState = SearchState.Idle(results = previewMovieResults),
      ),
      query = "Cast",
      onTextInput = {},
      onResultSelected = {},
      onForfeit = {},
      onDismissError = {},
    )
  }
}

@Preview(showBackground = true, name = "Empty chain")
@Composable
private fun GamePlayScreenEmptyPreview() {
  BaconsLawTheme {
    GamePlayScreenContent(
      uiState = UiState(
        currentPlayerDisplayText = "Alice",
        movesChain = emptyList(),
        searchState = SearchState.Idle(),
      ),
      query = "",
      onTextInput = {},
      onResultSelected = {},
      onForfeit = {},
      onDismissError = {},
    )
  }
}

@Preview(showBackground = true, name = "Searching")
@Composable
private fun GamePlayScreenSearchingPreview() {
  BaconsLawTheme {
    GamePlayScreenContent(
      uiState = UiState(
        currentPlayerDisplayText = "Alice",
        movesChain = previewChain,
        searchState = SearchState.Searching,
      ),
      query = "Cast Away",
      onTextInput = {},
      onResultSelected = {},
      onForfeit = {},
      onDismissError = {},
    )
  }
}

@Preview(showBackground = true, name = "Error")
@Composable
private fun GamePlayScreenErrorPreview() {
  BaconsLawTheme {
    GamePlayScreenContent(
      uiState = UiState(
        currentPlayerDisplayText = "Alice",
        movesChain = previewChain,
        searchState = SearchState.Error("Network error — check your connection"),
      ),
      query = "Cast Away",
      onTextInput = {},
      onResultSelected = {},
      onForfeit = {},
      onDismissError = {},
    )
  }
}

// endregion
