package com.zwsmith.bacons_law.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.zwsmith.bacons_law.data.Api
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch

class SearchViewModel : ViewModel() {
    var results = MutableStateFlow<List<String>>(emptyList())
    private val service = Api.create()

    fun searchMovies(query: String) {
        viewModelScope.launch {
            val results = service.searchMovies(query).results.map { it.title }
            this@SearchViewModel.results.value = results
        }
    }
}