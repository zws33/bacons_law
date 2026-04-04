package me.zwsmith.baconslaw.presentation

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedTextField
import androidx.compose.material.Text
import androidx.compose.material.TextFieldDefaults
import androidx.compose.material.darkColors
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.zwsmith.core.GameState
import me.zwsmith.core.Move
import me.zwsmith.core.Player

private val AppColors = darkColors(
  background = Color(18, 18, 18),
  surface = Color(28, 28, 28),
  primary = Color(255, 255, 255),
  secondary = Color(155, 155, 255),
)

@Composable
fun BaconsLawApp(viewModel: SearchViewModel) {
  val gameState by viewModel.gameState.collectAsStateWithLifecycle()
  val searchResults by viewModel.searchResults.collectAsStateWithLifecycle()
  MaterialTheme(colors = AppColors) {
    Column(
      modifier = Modifier
        .fillMaxSize()
        .background(MaterialTheme.colors.background)
        .padding(16.dp)
    ) {
      when (val state = gameState) {
        is GameState.GameOver -> {
          GameOverScreen(state)
        }

        is GameState.InProgress -> {
          PromptHeader(state)
          Spacer(Modifier.height(16.dp))
          SearchBox(viewModel.query, viewModel::onTextInput)
          Spacer(Modifier.height(8.dp))
          if (searchResults.isNotEmpty()) {
            ResultsList(searchResults, viewModel::onResultSelected)
          } else {
            ChainDisplay(state.moves)
          }
        }
      }
    }
  }
}

@Composable
fun ChainDisplay(moves: List<Move>) {
  if (moves.isEmpty()) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
      Text(
        text = "Name an Actor to start the chain!",
        color = MaterialTheme.colors.onSurface,
        fontSize = 14.sp
      )
    }
  } else {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
      items(moves) {
        ChainItem(it)
      }
    }
  }
}

@Composable
fun ResultsList(results: List<SearchResultItem>, onResultClicked: (SearchResultItem) -> Unit) {
  LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
    items(results) { item ->
      Row(
        modifier = Modifier
          .fillMaxWidth()
          .background(MaterialTheme.colors.surface, RoundedCornerShape(8.dp))
          .clickable { onResultClicked(item) }
          .padding(16.dp)
      ) {
        Text(
          text = item.displayText,
          color = MaterialTheme.colors.onSurface,
          fontSize = 16.sp
        )
      }
    }
  }
}

@Composable
private fun SearchBox(text: String, onTextInput: (String) -> Unit) {
  OutlinedTextField(
    modifier = Modifier.fillMaxWidth(),
    value = text,
    colors = TextFieldDefaults.textFieldColors(textColor = MaterialTheme.colors.onSurface),
    placeholder = { Text("Search...") },
    onValueChange = onTextInput,
    singleLine = true
  )
}


@Composable
fun PromptHeader(state: GameState.InProgress) {
  val prompt = when (val previousMove = state.moves.lastOrNull()) {
    is Move.Actor -> "Name a movie with ${previousMove.displayText}"
    is Move.Movie -> "Name an actor from ${previousMove.displayText}"
    null -> "Choose a starting actor"
  }
  val playerLabel = if (state.currentPlayer == Player.ONE) "Player 1" else "Player 2"
  Column {
    Text(
      text = playerLabel,
      color = MaterialTheme.colors.primary,
      style = MaterialTheme.typography.h4
    )
    Spacer(modifier = Modifier.height(8.dp))
    Text(
      text = prompt,
      color = MaterialTheme.colors.onSurface,
      style = MaterialTheme.typography.h4
    )
  }
}

@Composable
fun GameOverScreen(state: GameState.GameOver) {
  Column(
    modifier = Modifier
      .fillMaxSize()
      .padding(16.dp),
    horizontalAlignment = Alignment.CenterHorizontally,
    verticalArrangement = Arrangement.Center
  ) {
    val winnerLabel = if (state.winner == Player.ONE) "Player 1" else "Player 2"
    Text(
      text = "$winnerLabel wins!",
      color = MaterialTheme.colors.primary,
      style = MaterialTheme.typography.h4
    )
    Spacer(modifier = Modifier.height(24.dp))
    Text(
      text = "Moves",
      color = MaterialTheme.colors.onSurface,
      style = MaterialTheme.typography.subtitle1
    )
    Spacer(modifier = Modifier.height(8.dp))
    LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
      items(state.chain) {
        ChainItem(it)
      }
    }
  }
}

@Composable
fun ChainItem(item: Move) {
  val label = when (item) {
    is Move.Actor -> "Actor"
    is Move.Movie -> "Movie"
  }
  Column (
    modifier = Modifier
      .fillMaxWidth()
      .background(MaterialTheme.colors.surface)
      .padding(12.dp),
    horizontalAlignment = Alignment.Start,
    verticalArrangement = Arrangement.spacedBy(4.dp)
  ) {
    Text(
      text = label,
      color = MaterialTheme.colors.onSurface,
      style = MaterialTheme.typography.overline
    )
    Text(
      text = item.displayText, color = MaterialTheme.colors.onSurface,
      style = MaterialTheme.typography.body1
    )
  }
}

