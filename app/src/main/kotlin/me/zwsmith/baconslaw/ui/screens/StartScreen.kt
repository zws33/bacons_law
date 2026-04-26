package me.zwsmith.baconslaw.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.Button
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedTextField
import androidx.compose.material.Text
import androidx.compose.material.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import me.zwsmith.baconslaw.ui.components.TmdbAttribution

@Composable
internal fun StartScreen(
  onStart: (String, String) -> Unit,
  modifier: Modifier = Modifier
) {
  var playerOneName by remember { mutableStateOf("") }
  var playerTwoName by remember { mutableStateOf("") }
  Column(
    modifier = modifier
      .fillMaxSize()
      .padding(16.dp),
    horizontalAlignment = Alignment.CenterHorizontally,
  ) {
    Column(
      modifier = Modifier.weight(1f),
      verticalArrangement = Arrangement.Center,
      horizontalAlignment = Alignment.CenterHorizontally
    ) {
      OutlinedTextField(
        value = playerOneName,
        onValueChange = { playerOneName = it },
        label = { Text("Player 1 Name") },
        colors = TextFieldDefaults.outlinedTextFieldColors(textColor = MaterialTheme.colors.onSurface),
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
      )
      Spacer(Modifier.height(16.dp))
      OutlinedTextField(
        value = playerTwoName,
        onValueChange = { playerTwoName = it },
        label = { Text("Player 2 Name") },
        colors = TextFieldDefaults.outlinedTextFieldColors(textColor = MaterialTheme.colors.onSurface),
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
    TmdbAttribution(modifier = Modifier.padding(vertical = 8.dp))
  }
}
