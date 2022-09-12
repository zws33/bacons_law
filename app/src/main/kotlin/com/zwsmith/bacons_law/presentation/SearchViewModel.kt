package com.zwsmith.bacons_law.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.zwsmith.bacons_law.data.Api
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import timber.log.Timber

class SearchViewModel : ViewModel() {
    var castOfCurrentMovie = MutableStateFlow<List<String>>(emptyList())
    private val service = Api.create()

    fun playMove(query: String) {
        viewModelScope.launch {
            val id = searchMovies(query).firstOrNull()?.id
            val cast = id?.let { getCast(it) }
            if (cast != null) {
                castOfCurrentMovie.value = cast
            }
        }
    }

    private suspend fun searchMovies(query: String): List<GameMove.Movie> {
        return try {
            service.searchMovies(query).results.map { GameMove.Movie(it.id, it.title) }
        } catch (e: Throwable) {
            Timber.e(e)
            emptyList()
        }
    }

    private suspend fun getCast(movieId: Int): List<String> {
        return try {
            service.getCredits(movieId).cast.map { it.name }
        } catch (e: Throwable) {
            Timber.e(e)
            emptyList()
        }
    }
}

sealed class GameMove {
    data class Movie(val id: Int, val title: String) : GameMove()
    data class Actor(val id: Int, val name: String) : GameMove()
}