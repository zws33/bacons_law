package com.zwsmith.bacons_law.presentation

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.Button
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.material.TextField
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun BaconsLawApp(viewModel: SearchViewModel) {
    val results by viewModel.castOfCurrentMovie.collectAsState()
    MaterialTheme {
        Column(modifier = Modifier.fillMaxSize()) {
            SearchBox(viewModel::playMove)
            ResultsList(results)
        }
    }
}

@Composable
private fun ResultsList(titles: List<String>) {
    LazyColumn(
        modifier = Modifier.fillMaxWidth()
    ) {
        items(titles) { title ->
            Text(
                text = title,
                fontSize = 18.sp,
                fontWeight = FontWeight.Normal
            )
        }
    }
}

@Composable
private fun SearchBox(onClick: (String) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .height(56.dp)
    ) {
        var text by remember { mutableStateOf("") }
        TextField(
            modifier = Modifier.weight(3f),
            value = text,
            placeholder = { Text(text = "Search...") },
            onValueChange = { text = it },
        )
        Button(
            modifier = Modifier
                .weight(1f)
                .fillMaxHeight(),
            onClick = { onClick(text) }
        ) {
            Text("Search")
        }
    }
}