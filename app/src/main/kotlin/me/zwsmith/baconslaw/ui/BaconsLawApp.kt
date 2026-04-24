package me.zwsmith.baconslaw.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.zwsmith.baconslaw.ui.screens.GameScreen
import me.zwsmith.baconslaw.ui.screens.StartScreen
import me.zwsmith.baconslaw.ui.theme.BaconsLawTheme

@Composable
fun BaconsLawApp(viewModel: GameViewModel) {
  val playerNames by viewModel.playerNames.collectAsStateWithLifecycle()

  BaconsLawTheme {
    if (playerNames == null) {
      StartScreen(onStart = { p1, p2 -> viewModel.startGame(p1, p2) })
    } else {
      val (p1Name, p2Name) = playerNames!!
      GameScreen(viewModel, p1Name, p2Name)
    }
  }
}
