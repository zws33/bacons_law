package me.zwsmith.baconslaw.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.CircularProgressIndicator
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.zwsmith.baconslaw.ui.GameViewModel
import me.zwsmith.baconslaw.ui.GameUiState
import me.zwsmith.baconslaw.ui.components.ChainDisplay
import me.zwsmith.baconslaw.ui.components.ErrorMessage
import me.zwsmith.baconslaw.ui.components.PromptHeader
import me.zwsmith.baconslaw.ui.components.ResultsList
import me.zwsmith.baconslaw.ui.components.SearchBox
import me.zwsmith.core.GameState
import me.zwsmith.core.Player

@Composable
internal fun GameScreen(
  viewModel: GameViewModel,
  p1Name: String,
  p2Name: String
) {
  val gameState by viewModel.gameState.collectAsStateWithLifecycle()
  val uiState by viewModel.uiState.collectAsStateWithLifecycle()
  val isSubmitting by viewModel.isSubmitting.collectAsStateWithLifecycle()

  Column(
    modifier = Modifier
      .fillMaxSize()
      .background(MaterialTheme.colors.background)
      .padding(16.dp)
  ) {
    when (val state = gameState) {
      is GameState.GameOver -> {
        val winnerName = if (state.winner == Player.ONE) p1Name else p2Name
        GameOverScreen(state, winnerName, onPlayAgain = viewModel::resetGame)
      }

      is GameState.InProgress -> {
        val currentPlayerName = if (state.currentPlayer == Player.ONE) p1Name else p2Name
        PromptHeader(state, currentPlayerName)
        Spacer(Modifier.height(16.dp))
        SearchBox(viewModel.query, viewModel::onTextInput, enabled = !isSubmitting)
        Spacer(Modifier.height(8.dp))

        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
          when (val stateUi = uiState) {
            is GameUiState.Loading -> {
              CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            }

            is GameUiState.Success -> {
              if (stateUi.results.isEmpty() && viewModel.query.isNotBlank()) {
                Text(
                  text = "No results found for \"${viewModel.query}\"",
                  color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
                  modifier = Modifier.align(Alignment.Center)
                )
              } else {
                ResultsList(stateUi.results, viewModel::onResultSelected)
              }
            }

            is GameUiState.Error -> {
              ErrorMessage(stateUi.message, onDismiss = viewModel::reset)
            }

            is GameUiState.Idle -> {
              if (isSubmitting) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
              } else {
                ChainDisplay(state.moves)
              }
            }
          }
        }
        Spacer(Modifier.height(8.dp))
        OutlinedButton(
          onClick = viewModel::forfeit,
          enabled = !isSubmitting,
          modifier = Modifier.fillMaxWidth()
        ) {
          Text("I can't answer")
        }
      }
    }
  }
}
