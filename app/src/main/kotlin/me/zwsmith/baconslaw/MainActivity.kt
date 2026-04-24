package me.zwsmith.baconslaw

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.viewmodel.compose.viewModel
import me.zwsmith.baconslaw.ui.BaconsLawApp
import me.zwsmith.baconslaw.ui.GameViewModel

class MainActivity : ComponentActivity() {

  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    setContent {
      BaconsLawApp(viewModel(factory = GameViewModel.Factory))
    }
  }
}

