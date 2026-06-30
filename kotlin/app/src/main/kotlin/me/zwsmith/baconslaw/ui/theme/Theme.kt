package me.zwsmith.baconslaw.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val black = Color(18, 18, 18)
private val AppColorScheme = darkColorScheme(
  background = black,
  surface = Color(28, 28, 28),
  primary = Color(255, 255, 255),
  secondary = Color(155, 155, 255),
  onPrimary = black
)

@Composable
fun BaconsLawTheme(content: @Composable () -> Unit) {
  MaterialTheme(
    colorScheme = AppColorScheme,
    content = content
  )
}
