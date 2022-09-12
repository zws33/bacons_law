package com.zwsmith.bacons_law.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.zwsmith.bacons_law.data.Api
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import timber.log.Timber

class SearchViewModel : ViewModel() {
    private val service = Api.create()

    private val _searchResults = MutableStateFlow<List<String>>(emptyList())
    val searchResults: StateFlow<List<String>> = _searchResults

    private val _currentMoveType: MutableStateFlow<GameMove> = MutableStateFlow(GameMove.Movie)
    val currentMoveType: StateFlow<GameMove> = _currentMoveType
    private val _query: MutableStateFlow<String> = MutableStateFlow("")
    val query: StateFlow<String> = _query

    private fun resetSearch() {
        _searchResults.value = emptyList()
        _query.value = ""
    }

    fun setMovieSearch() {
        _currentMoveType.value = GameMove.Movie
        onTextInput(query.value)
    }

    fun setActorSearch() {
        _currentMoveType.value = GameMove.Actor
        onTextInput(query.value)
    }

    fun onTextInput(query: String) {
        _query.value = query
        viewModelScope.launch {
            when (currentMoveType.value) {
                GameMove.Movie -> {
                    viewModelScope.launch {
                        val results: List<Movie> = searchMovies(query)
                        _searchResults.value = results.map { it.title }
                    }
                }
                GameMove.Actor -> {
                    viewModelScope.launch {
                        val results: List<Actor> = searchActors(query)
                        _searchResults.value = results.map { it.name }
                    }
                }
            }
        }
    }

    private suspend fun searchActors(query: String): List<Actor> {
        return try {
            service.searchActor(query).results.map { Actor(it.id, it.name) }
        } catch (e: Throwable) {
            Timber.e(e)
            emptyList()
        }
    }

    private suspend fun searchMovies(query: String): List<Movie> {
        return try {
            service.searchMovies(query).results.map { Movie(it.id, it.title) }
        } catch (e: Throwable) {
            Timber.e(e)
            emptyList()
        }
    }

    private suspend fun getCastByMovieId(movieId: Int): List<Actor> {
        return try {
            service.getCredits(movieId).cast.map { Actor(it.id, it.name) }
        } catch (e: Throwable) {
            Timber.e(e)
            emptyList()
        }
    }
}

data class Movie(val id: Int, val title: String)
data class Actor(val id: Int, val name: String)

enum class GameMove {
    Movie,
    Actor
}