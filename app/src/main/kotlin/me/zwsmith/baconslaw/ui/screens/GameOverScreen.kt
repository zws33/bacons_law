package me.zwsmith.baconslaw.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import me.zwsmith.baconslaw.ui.components.TmdbAttribution

@Composable
internal fun GameOverScreen(
  winnerName: String,
  viewModel: GameOverViewModel,
  onPlayAgain: () -> Unit,
  modifier: Modifier = Modifier,
) {
  Column(
    modifier = modifier
      .fillMaxSize()
      .padding(bottom = 8.dp),
    horizontalAlignment = Alignment.CenterHorizontally,
  ) {
    Column(
      modifier = Modifier
        .weight(1f)
        .fillMaxWidth()
        .padding(horizontal = 16.dp),
      horizontalAlignment = Alignment.CenterHorizontally,
      verticalArrangement = Arrangement.Center,
    ) {
      Text(
        text = "$winnerName wins!",
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        style = MaterialTheme.typography.displayMedium,
      )
      Spacer(modifier = Modifier.height(32.dp))
      Button(
        onClick = {
          viewModel.reset()
          onPlayAgain()
        },
        modifier = Modifier.fillMaxWidth(),
      ) {
        Text(
          text = "Play Again",
          color = MaterialTheme.colorScheme.onPrimary,
          style = MaterialTheme.typography.bodyLarge
        )
      }
    }
    TmdbAttribution()
  }
}
