package me.zwsmith.baconslaw.ui

import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material.AppBarDefaults
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Scaffold
import androidx.compose.material.Surface
import androidx.compose.material.Text
import androidx.compose.material.TopAppBar
import androidx.compose.material.primarySurface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.zwsmith.baconslaw.ui.screens.GameScreen
import me.zwsmith.baconslaw.ui.screens.StartScreen
import me.zwsmith.baconslaw.ui.theme.BaconsLawTheme

@Composable
fun BaconsLawApp(viewModel: GameViewModel) {
  val playerNames by viewModel.playerNames.collectAsStateWithLifecycle()

  BaconsLawTheme {
    Scaffold(
      topBar = {
        Surface(
          color = MaterialTheme.colors.primarySurface,
          elevation = AppBarDefaults.TopAppBarElevation
        ) {
          TopAppBar(
            title = { Text("Bacon's Law") },
            modifier = Modifier.windowInsetsPadding(
              WindowInsets.statusBars.only(WindowInsetsSides.Top)
            ),
            backgroundColor = Color.Transparent,
            elevation = 0.dp
          )
        }
      }
    ) { paddingValues ->
      val contentModifier = Modifier
        .padding(paddingValues)
        .windowInsetsPadding(WindowInsets.navigationBars)

      if (playerNames == null) {
        StartScreen(
          onStart = { p1, p2 -> viewModel.startGame(p1, p2) },
          modifier = contentModifier
        )
      } else {
        val (p1Name, p2Name) = playerNames!!
        GameScreen(viewModel, p1Name, p2Name, modifier = contentModifier)
      }
    }
  }
}
