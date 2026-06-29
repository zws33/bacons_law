@file:OptIn(ExperimentalMaterial3Api::class)

package me.zwsmith.baconslaw.ui

import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.toRoute
import me.zwsmith.baconslaw.ui.screens.GameOverScreen
import me.zwsmith.baconslaw.ui.screens.GameOverViewModel
import me.zwsmith.baconslaw.ui.screens.GamePlayScreen
import me.zwsmith.baconslaw.ui.screens.StartScreen
import me.zwsmith.baconslaw.ui.screens.StartScreenViewModel
import me.zwsmith.baconslaw.ui.theme.BaconsLawTheme

@Composable
fun BaconsLawApp() {
  val navController = rememberNavController()

  BaconsLawTheme {
    Scaffold(
      topBar = {
        CenterAlignedTopAppBar(
          title = { Text("Bacon's Law") },
          modifier = Modifier.windowInsetsPadding(
            WindowInsets.statusBars.only(WindowInsetsSides.Top)
          ),
        )
      }
    ) { paddingValues ->
      val contentModifier = Modifier
        .padding(paddingValues)
        .windowInsetsPadding(WindowInsets.navigationBars)
      NavHost(navController, startDestination = GameStart) {
        composable<GameStart> {
          StartScreen(
            modifier = contentModifier,
            viewModel = viewModel<StartScreenViewModel>(factory = StartScreenViewModel.Factory),
            onStartGameEvent = {
              navController.navigate(InProgress)
            },
          )
        }
        composable<InProgress> {
          GamePlayScreen(
            modifier = contentModifier,
            viewModel = viewModel(factory = GameplayViewModel.Factory),
            onGameOver = { winnerName ->
              navController.navigate(GameOver(winnerName)) {
                popUpTo<GameStart>()
              }
            },
          )
        }
        composable<GameOver> { backStackEntry ->
          val route = backStackEntry.toRoute<GameOver>()
          GameOverScreen(
            winnerName = route.winner,
            modifier = contentModifier,
            viewModel = viewModel(factory = GameOverViewModel.Factory),
            onPlayAgain = {
              navController.navigate(GameStart) {
                popUpTo<GameStart> { inclusive = true }
              }
            },
          )
        }
      }
    }
  }
}
