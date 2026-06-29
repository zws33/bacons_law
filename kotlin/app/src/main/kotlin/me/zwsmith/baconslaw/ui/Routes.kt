package me.zwsmith.baconslaw.ui

import kotlinx.serialization.Serializable

@Serializable
data object GameStart

@Serializable
data object InProgress

@Serializable
data class GameOver(
  val winner: String
)
