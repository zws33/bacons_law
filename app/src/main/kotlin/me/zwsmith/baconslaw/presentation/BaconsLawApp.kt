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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.Button
import androidx.compose.material.CircularProgressIndicator
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.OutlinedTextField
import androidx.compose.material.Text
import androidx.compose.material.TextFieldDefaults
import androidx.compose.material.darkColors
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import me.zwsmith.core.GameState
import me.zwsmith.core.Move
import me.zwsmith.core.Player

private const val TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w185"

private val AppColors = darkColors(
  background = Color(18, 18, 18),
  surface = Color(28, 28, 28),
  primary = Color(255, 255, 255),
  secondary = Color(155, 155, 255),
)

@Composable
fun BaconsLawApp(viewModel: GameViewModel) {
  val playerNames by viewModel.playerNames.collectAsStateWithLifecycle()

  MaterialTheme(colors = AppColors) {
    if (playerNames == null) {
      StartScreen(onStart = { p1, p2 -> viewModel.startGame(p1, p2) })
    } else {
      val (p1Name, p2Name) = playerNames!!
      GameScreen(viewModel, p1Name, p2Name)
    }
  }
}

@Composable
fun GameScreen(
  viewModel: GameViewModel,
  p1Name: String,
  p2Name: String
) {
  val gameState by viewModel.gameState.collectAsStateWithLifecycle()
  val searchUiState by viewModel.searchUiState.collectAsStateWithLifecycle()
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
          when (val uiState = searchUiState) {
            is SearchUiState.Loading -> {
              CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            }

            is SearchUiState.Success -> {
              if (uiState.results.isEmpty() && viewModel.query.isNotBlank()) {
                Text(
                  text = "No results found for \"${viewModel.query}\"",
                  color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
                  modifier = Modifier.align(Alignment.Center)
                )
              } else {
                ResultsList(uiState.results, viewModel::onResultSelected)
              }
            }

            is SearchUiState.Error -> {
              ErrorMessage(uiState.message, onDismiss = viewModel::reset)
            }

            is SearchUiState.Idle -> {
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

@Composable
fun StartScreen(onStart: (String, String) -> Unit) {
  var playerOneName by remember { mutableStateOf("") }
  var playerTwoName by remember { mutableStateOf("") }
  Column(
    modifier = Modifier
      .fillMaxSize()
      .background(MaterialTheme.colors.background)
      .padding(16.dp),
    horizontalAlignment = Alignment.CenterHorizontally,
    verticalArrangement = Arrangement.Center
  ) {
    Text(
      text = "Bacon's Law",
      color = MaterialTheme.colors.primary,
      style = MaterialTheme.typography.h3
    )
    Spacer(Modifier.height(32.dp))
    OutlinedTextField(
      value = playerOneName,
      onValueChange = { playerOneName = it },
      label = { Text("Player 1 Name") },
      colors = TextFieldDefaults.textFieldColors(textColor = MaterialTheme.colors.onSurface),
      singleLine = true,
      modifier = Modifier.fillMaxWidth()
    )
    Spacer(Modifier.height(16.dp))
    OutlinedTextField(
      value = playerTwoName,
      onValueChange = { playerTwoName = it },
      label = { Text("Player 2 Name") },
      colors = TextFieldDefaults.textFieldColors(textColor = MaterialTheme.colors.onSurface),
      singleLine = true,
      modifier = Modifier.fillMaxWidth()
    )
    Spacer(Modifier.height(32.dp))
    Button(
      onClick = { onStart(playerOneName.trim(), playerTwoName.trim()) },
      enabled = playerOneName.isNotBlank() && playerTwoName.isNotBlank(),
      modifier = Modifier.fillMaxWidth()
    ) {
      Text("Start Game")
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
          .padding(8.dp),
        verticalAlignment = Alignment.CenterVertically
      ) {
        AsyncImage(
          model = TMDB_IMAGE_BASE_URL + item.imagePath,
          contentDescription = null,
          modifier = Modifier
            .size(60.dp, 90.dp)
            .clip(RoundedCornerShape(4.dp))
            .background(Color.Gray),
          contentScale = ContentScale.Crop
        )
        Spacer(Modifier.width(12.dp))
        Column {
          Text(
            text = item.displayText,
            color = MaterialTheme.colors.onSurface,
            fontSize = 16.sp
          )
          item.releaseYear?.let {
            Text(
              text = it,
              color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
              fontSize = 14.sp
            )
          }
        }
      }
    }
  }
}

@Composable
private fun SearchBox(text: String, onTextInput: (String) -> Unit, enabled: Boolean = true) {
  OutlinedTextField(
    modifier = Modifier.fillMaxWidth(),
    value = text,
    enabled = enabled,
    colors = TextFieldDefaults.textFieldColors(textColor = MaterialTheme.colors.onSurface),
    placeholder = { Text("Search...") },
    onValueChange = onTextInput,
    singleLine = true
  )
}

@Composable
private fun ErrorMessage(message: String, onDismiss: () -> Unit) {
  Row(
    modifier = Modifier
      .fillMaxWidth()
      .background(Color(120, 30, 30), RoundedCornerShape(8.dp))
      .padding(horizontal = 12.dp, vertical = 8.dp),
    verticalAlignment = Alignment.CenterVertically
  ) {
    Text(
      text = message,
      color = Color.White,
      fontSize = 14.sp,
      modifier = Modifier.weight(1f)
    )
    Spacer(Modifier.width(8.dp))
    Text(
      text = "Dismiss",
      color = Color.White.copy(alpha = 0.8f),
      fontSize = 12.sp,
      modifier = Modifier.clickable { onDismiss() }
    )
  }
}

@Composable
fun PromptHeader(state: GameState.InProgress, currentPlayerName: String) {
  val prompt = when (val previousMove = state.moves.lastOrNull()) {
    is Move.Actor -> "Name a movie with ${previousMove.displayText}"
    is Move.Movie -> "Name an actor from ${previousMove.displayText}"
    null -> "Choose a starting actor"
  }
  Column {
    Text(
      text = currentPlayerName,
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
fun GameOverScreen(state: GameState.GameOver, winnerName: String, onPlayAgain: () -> Unit) {
  Column(
    modifier = Modifier
      .fillMaxSize()
      .padding(16.dp),
    horizontalAlignment = Alignment.CenterHorizontally,
    verticalArrangement = Arrangement.Center
  ) {
    Text(
      text = "$winnerName wins!",
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
    LazyColumn(
      modifier = Modifier.weight(1f),
      verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
      items(state.chain) {
        ChainItem(it)
      }
    }
    Spacer(modifier = Modifier.height(16.dp))
    Button(
      onClick = onPlayAgain,
      modifier = Modifier.fillMaxWidth()
    ) {
      Text("Play Again")
    }
  }
}

@Composable
fun ChainItem(item: Move) {
  val label = when (item) {
    is Move.Actor -> "Actor"
    is Move.Movie -> "Movie"
  }
  Row(
    modifier = Modifier
      .fillMaxWidth()
      .background(MaterialTheme.colors.surface, RoundedCornerShape(8.dp))
      .padding(8.dp),
    verticalAlignment = Alignment.CenterVertically
  ) {
    AsyncImage(
      model = TMDB_IMAGE_BASE_URL + item.imagePath,
      contentDescription = null,
      modifier = Modifier
        .size(60.dp, 90.dp)
        .clip(RoundedCornerShape(4.dp))
        .background(Color.Gray),
      contentScale = ContentScale.Crop
    )
    Spacer(Modifier.width(12.dp))
    Column(
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
      if (item is Move.Movie) {
        item.releaseYear?.let {
          Text(
            text = it,
            color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
            style = MaterialTheme.typography.body2
          )
        }
      }
    }
  }
}
