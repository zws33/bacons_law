package me.zwsmith.baconslaw.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.InputChip
import androidx.compose.material3.InputChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.flow.filterIsInstance
import me.zwsmith.baconslaw.data.GameSession
import me.zwsmith.baconslaw.domain.PlayerInfo
import me.zwsmith.baconslaw.ui.components.TmdbAttribution
import me.zwsmith.baconslaw.ui.theme.BaconsLawTheme

@Composable
internal fun StartScreen(
  modifier: Modifier = Modifier,
  viewModel: StartScreenViewModel,
  onStartGameEvent: () -> Unit
) {
  val uiState by viewModel.uiState.collectAsStateWithLifecycle()
  LaunchedEffect(Unit) {
    viewModel.onStartEvent.filterIsInstance<GameSession.InProgress>().collect { onStartGameEvent() }
  }
  StartScreenContent(
    modifier = modifier,
    playerNames = uiState.players,
    onAddPlayerClick = { name -> viewModel.onAddPlayer(name) },
    onStartClick = viewModel::onStart,
    onRemovePlayer = { id -> viewModel.onRemovePlayer(id) }
  )
}

@Composable
private fun StartScreenContent(
  modifier: Modifier = Modifier,
  playerNames: List<PlayerInfo>,
  onRemovePlayer: (String) -> Unit,
  onAddPlayerClick: (String) -> Unit,
  onStartClick: () -> Unit
) {
  var player by remember { mutableStateOf("") }
  Column(
    modifier = modifier
      .fillMaxSize()
      .padding(16.dp),
    verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.Bottom),
    horizontalAlignment = Alignment.CenterHorizontally
  ) {
    FlowRow(
      modifier = Modifier.fillMaxWidth(),
      horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
      playerNames.forEach { playerInfo ->
        InputChip(
          selected = true,
          onClick = { onRemovePlayer(playerInfo.id) },
          avatar = {
            Icon(Icons.Default.Person, contentDescription = null)
          },
          label = {
            Text(playerInfo.displayName)
          },
          trailingIcon = {
            Icon(
              modifier = Modifier.size(InputChipDefaults.IconSize),
              imageVector = Icons.Default.Close,
              contentDescription = null
            )
          },
        )
      }
    }
    OutlinedTextField(
      value = player,
      onValueChange = { player = it },
      placeholder = { Text("Player Name") },
      singleLine = true,
      modifier = Modifier.fillMaxWidth(),
      keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
      trailingIcon = {
        IconButton(onClick = {
          if (player.isNotEmpty()) {
            onAddPlayerClick(player)
            player = ""
          }
        }) {
          Icon(imageVector = Icons.Default.Add, contentDescription = null)
        }
      }
    )
    Button(
      onClick = { onStartClick() },
      enabled = playerNames.size > 1,
      modifier = Modifier.fillMaxWidth(),
      colors = ButtonDefaults.buttonColors(
        contentColor = MaterialTheme.colorScheme.onSecondary,
        containerColor = MaterialTheme.colorScheme.secondary
      )
    ) {
      Text("Start Game")
    }
    TmdbAttribution(modifier = Modifier.padding(vertical = 8.dp))
  }
}

@Preview(name = "Start screen", showBackground = true)
@Composable
fun StartScreenPreview() {
  BaconsLawTheme {
    Surface(modifier = Modifier.fillMaxSize()) {
      StartScreenContent(
        playerNames = listOf(
          "Zach",
          "Molly",
          "Sana",
          "Yousuf",
          "Madiha"
        ).mapIndexed { index, string -> PlayerInfo(index.toString(), string) },
        onAddPlayerClick = {},
        onStartClick = {},
        onRemovePlayer = {}
      )
    }
  }
}
