package me.zwsmith.baconslaw.ui.theme

import androidx.compose.material.MaterialTheme
import androidx.compose.material.darkColors
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val AppColors = darkColors(
  background = Color(18, 18, 18),
  surface = Color(28, 28, 28),
  primary = Color(255, 255, 255),
  secondary = Color(155, 155, 255),
)

@Composable
fun BaconsLawTheme(content: @Composable () -> Unit) {
  MaterialTheme(
    colors = AppColors,
    content = content
  )
}
