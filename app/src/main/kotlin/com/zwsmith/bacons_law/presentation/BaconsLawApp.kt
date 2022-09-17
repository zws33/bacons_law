package com.zwsmith.bacons_law.presentation

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.MaterialTheme
import androidx.compose.material.RadioButton
import androidx.compose.material.Text
import androidx.compose.material.TextField
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun BaconsLawApp(viewModel: SearchViewModel) {
    val results by viewModel.searchResults.collectAsState()
    val move by viewModel.currentMoveType.collectAsState()
    MaterialTheme {
        Column(modifier = Modifier.fillMaxSize()) {
            Row {
                Row {
                    RadioButton(selected = move == GameMove.Movie, onClick = viewModel::setMovieSearch)
                    Text("Movie", Modifier.padding(16.dp))
                }
                Row {
                    RadioButton(selected = move == GameMove.Actor, onClick = viewModel::setActorSearch)
                    Text("Actor", Modifier.padding(16.dp))
                }
            }
            SearchBox(viewModel.query, viewModel::onTextInput)
            ResultsList(results = results)
        }
    }
}

@Composable
private fun ResultsList(results: List<String>) {
    LazyColumn(
        modifier = Modifier.fillMaxWidth()
    ) {
        items(results) { title ->
            Text(
                text = title,
                fontSize = 18.sp,
                fontWeight = FontWeight.Normal
            )
        }
    }
}

@Composable
private fun SearchBox(text: String, onTextInput: (String) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .height(56.dp)
    ) {
        TextField(
            modifier = Modifier.weight(3f),
            value = text,
            placeholder = { Text(text = "Search...") },
            onValueChange = {
                onTextInput(it)
            },
        )
    }
}