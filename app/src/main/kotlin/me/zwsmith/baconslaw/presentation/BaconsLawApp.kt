package me.zwsmith.baconslaw.presentation

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedTextField
import androidx.compose.material.Text
import androidx.compose.material.TextFieldDefaults
import androidx.compose.material.darkColors
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun BaconsLawApp(viewModel: SearchViewModel) {
  val results by viewModel.searchResults.collectAsState()
  val move by viewModel.currentMoveType.collectAsState()
  val AppColors = darkColors(
    background = Color(18, 18, 18),
    surface = Color(28, 28, 28),
    primary = Color(0xFF81D4FA),
    secondary = Color(0xFFFFAB91)
  )
  MaterialTheme(colors = AppColors) {
    Column(
      modifier = Modifier
        .fillMaxSize()
        .background(MaterialTheme.colors.background),
    ) {
      Spacer(modifier = Modifier.height(16.dp))
      SearchBox(viewModel.query, viewModel::onTextInput)
      SearchTypeSelector(
        currentMove = move,
        viewModel = viewModel,
        modifier = Modifier.fillMaxWidth()
      )
      var selected by remember {
        mutableStateOf(emptyList<String>())
      }
      if (viewModel.query.isNotEmpty()) {
        ResultsList(results = results, onClick = {
          selected = selected.plus(it)
          viewModel.reset()
        })
      } else {
        SelectionList(selected)
      }
      Spacer(modifier = Modifier.height(16.dp))

    }
  }
}

@Composable
private fun SearchTypeSelector(
  currentMove: GameMove,
  viewModel: SearchViewModel,
  modifier: Modifier = Modifier,
) {
  Box(
    modifier = Modifier
      .border(
        width = 2.dp,
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colors.surface
      )
      .clip(RoundedCornerShape(8.dp))
  ) {
    Row(modifier = modifier, horizontalArrangement = Arrangement.SpaceAround) {
      Box(
        modifier = Modifier
          .weight(1f)
          .background(color = getBackgroundColor(currentMove == GameMove.Movie))
          .padding(16.dp)
          .clickable(onClick = viewModel::setMovieSearch),
        contentAlignment = Alignment.Center
      ) {
        Text(
          text = "Movie",
          modifier = Modifier
            .padding(horizontal = 4.dp),
          color = getTextColor(currentMove == GameMove.Movie),
          fontSize = 16.sp
        )
      }
      Box(
        modifier = Modifier
          .weight(1f)
          .background(color = getBackgroundColor(currentMove == GameMove.Actor))
          .padding(16.dp)
          .clickable(onClick = viewModel::setActorSearch),
        contentAlignment = Alignment.Center
      ) {
        Text(
          text = "Actor",
          modifier = Modifier
            .padding(horizontal = 4.dp),
          color = getTextColor(currentMove == GameMove.Actor),
          fontSize = 16.sp
        )
      }
    }
  }
}

@Composable
private fun getTextColor(isSelected: Boolean) =
  if (isSelected) MaterialTheme.colors.onPrimary else MaterialTheme.colors.onSurface

@Composable
private fun getBackgroundColor(isSelected: Boolean) =
  if (isSelected) MaterialTheme.colors.primary else MaterialTheme.colors.surface

@Composable
fun SelectionList(selected: List<String>) {
  LazyColumn(
    modifier = Modifier.fillMaxWidth(),
    verticalArrangement = Arrangement.spacedBy(4.dp)
  ) {
    items(selected) { title ->
      ListItem(title = title, onClick = {})
    }
  }
}

@Composable
private fun ResultsList(results: List<String>, onClick: (String) -> Unit) {
  LazyColumn(
    modifier = Modifier.fillMaxWidth(),
    verticalArrangement = Arrangement.spacedBy(4.dp)
  ) {
    items(results) { title ->
      ListItem(title = title, onClick = onClick)
    }
  }
}

@Composable
private fun ListItem(title: String, onClick: (String) -> Unit) {
  Card {
    Box(
      Modifier
        .padding(16.dp)
        .fillMaxWidth()
        .clickable { onClick(title) }
    ) {
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
    OutlinedTextField(
      modifier = Modifier.weight(3f),
      value = text,
      colors = TextFieldDefaults.textFieldColors(textColor = MaterialTheme.colors.onSurface),
      placeholder = { Text(text = "Search...") },
      onValueChange = {
        onTextInput(it)
      },
    )
  }
}
