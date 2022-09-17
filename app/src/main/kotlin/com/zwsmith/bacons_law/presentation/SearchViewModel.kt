package com.zwsmith.bacons_law.presentation

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.zwsmith.bacons_law.data.Api
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import timber.log.Timber

class SearchViewModel(val repository: Repository) : ViewModel() {

    private val _searchResults = MutableStateFlow<List<String>>(emptyList())
    val searchResults: StateFlow<List<String>> = _searchResults

    private val _currentMoveType: MutableStateFlow<GameMove> = MutableStateFlow(GameMove.Movie)
    val currentMoveType: StateFlow<GameMove> = _currentMoveType

    var query by mutableStateOf("")
        private set

    fun setMovieSearch() {
        _currentMoveType.value = GameMove.Movie
        onTextInput(query)
    }

    fun setActorSearch() {
        _currentMoveType.value = GameMove.Actor
        onTextInput(query)
    }

    fun onTextInput(query: String) {
        this.query = query
        viewModelScope.launch {
            when (currentMoveType.value) {
                GameMove.Movie -> {
                    viewModelScope.launch {
                        val results: List<Movie> = repository.searchMovies(query)
                        _searchResults.value = results.map { it.title }
                    }
                }
                GameMove.Actor -> {
                    viewModelScope.launch {
                        val results: List<Actor> = repository.searchActors(query)
                        _searchResults.value = results.map { it.name }
                    }
                }
            }
        }
    }
}

data class Movie(val id: Int, val title: String)
data class Actor(val id: Int, val name: String)

enum class GameMove {
    Movie,
    Actor
}