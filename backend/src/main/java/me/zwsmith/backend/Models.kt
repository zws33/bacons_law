package me.zwsmith.backend

import kotlinx.serialization.Serializable

@Serializable
data class MovieSearchResult(val id: Int, val title: String)

@Serializable
data class PersonSearchResult(val id: Int, val name: String)

@Serializable
data class MovieCreditsResult(val id: Int, val castIds: List<Int>)
