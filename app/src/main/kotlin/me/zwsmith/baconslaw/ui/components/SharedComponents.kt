package me.zwsmith.baconslaw.ui.components

import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedTextField
import androidx.compose.material.Text
import androidx.compose.material.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import me.zwsmith.baconslaw.ui.SearchResultItem
import me.zwsmith.core.GameState
import me.zwsmith.core.Move

@Composable
internal fun ChainDisplay(moves: List<Move>) {
  if (moves.isEmpty()) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
      Text(
        text = "Name an Actor to start the chain!",
        color = MaterialTheme.colors.onSurface,
        fontSize = 14.sp
      )
    }
  } else {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
      items(moves) {
        ChainItem(it)
      }
    }
  }
}

@Composable
internal fun ResultsList(results: List<SearchResultItem>, onResultClicked: (SearchResultItem) -> Unit) {
  LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
    items(results) { item ->
      Row(
        modifier = Modifier
          .fillMaxWidth()
          .background(MaterialTheme.colors.surface, RoundedCornerShape(8.dp))
          .clickable { onResultClicked(item) }
          .padding(8.dp),
        verticalAlignment = Alignment.CenterVertically
      ) {
        AsyncImage(
          model = item.imagePath,
          contentDescription = null,
          modifier = Modifier
            .size(60.dp, 90.dp)
            .clip(RoundedCornerShape(4.dp))
            .background(Color.Gray),
          contentScale = ContentScale.Crop
        )
        Spacer(Modifier.width(12.dp))
        Column {
          Text(
            text = item.displayText,
            color = MaterialTheme.colors.onSurface,
            fontSize = 16.sp
          )
          item.releaseYear?.let {
            Text(
              text = it,
              color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
              fontSize = 14.sp
            )
          }
        }
      }
    }
  }
}

@Composable
internal fun SearchBox(text: String, onTextInput: (String) -> Unit, enabled: Boolean = true) {
  OutlinedTextField(
    modifier = Modifier.fillMaxWidth(),
    value = text,
    enabled = enabled,
    colors = TextFieldDefaults.textFieldColors(textColor = MaterialTheme.colors.onSurface),
    placeholder = { Text("Search...") },
    onValueChange = onTextInput,
    singleLine = true
  )
}

@Composable
internal fun ErrorMessage(message: String, onDismiss: () -> Unit) {
  Row(
    modifier = Modifier
      .fillMaxWidth()
      .background(Color(120, 30, 30), RoundedCornerShape(8.dp))
      .padding(horizontal = 12.dp, vertical = 8.dp),
    verticalAlignment = Alignment.CenterVertically
  ) {
    Text(
      text = message,
      color = Color.White,
      fontSize = 14.sp,
      modifier = Modifier.weight(1f)
    )
    Spacer(Modifier.width(8.dp))
    Text(
      text = "Dismiss",
      color = Color.White.copy(alpha = 0.8f),
      fontSize = 12.sp,
      modifier = Modifier.clickable { onDismiss() }
    )
  }
}

@Composable
internal fun PromptHeader(state: GameState.InProgress, currentPlayerName: String) {
  val prompt = when (val previousMove = state.moves.lastOrNull()) {
    is Move.Actor -> "Name a movie with ${previousMove.displayText}"
    is Move.Movie -> "Name an actor from ${previousMove.displayText}"
    null -> "Choose a starting actor"
  }
  Column {
    Text(
      text = currentPlayerName,
      color = MaterialTheme.colors.primary,
      style = MaterialTheme.typography.h4
    )
    Spacer(modifier = Modifier.height(8.dp))
    Text(
      text = prompt,
      color = MaterialTheme.colors.onSurface,
      style = MaterialTheme.typography.h4
    )
  }
}

@Composable
internal fun ChainItem(item: Move) {
  val label = when (item) {
    is Move.Actor -> "Actor"
    is Move.Movie -> "Movie"
  }
  Row(
    modifier = Modifier
      .fillMaxWidth()
      .background(MaterialTheme.colors.surface, RoundedCornerShape(8.dp))
      .padding(8.dp),
    verticalAlignment = Alignment.CenterVertically
  ) {
    AsyncImage(
      model = item.imagePath,
      contentDescription = null,
      modifier = Modifier
        .size(60.dp, 90.dp)
        .clip(RoundedCornerShape(4.dp))
        .background(Color.Gray),
      contentScale = ContentScale.Crop
    )
    Spacer(Modifier.width(12.dp))
    Column(
      horizontalAlignment = Alignment.Start,
      verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
      Text(
        text = label,
        color = MaterialTheme.colors.onSurface,
        style = MaterialTheme.typography.overline
      )
      Text(
        text = item.displayText, color = MaterialTheme.colors.onSurface,
        style = MaterialTheme.typography.body1
      )
      if (item is Move.Movie) {
        item.releaseYear?.let {
          Text(
            text = it,
            color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
            style = MaterialTheme.typography.body2
          )
        }
      }
    }
  }
}
