package me.zwsmith.baconslaw.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.Button
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import me.zwsmith.baconslaw.ui.components.ChainItem
import me.zwsmith.core.GameState

@Composable
internal fun GameOverScreen(state: GameState.GameOver, winnerName: String, onPlayAgain: () -> Unit) {
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
