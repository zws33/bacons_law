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
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
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
        style = MaterialTheme.typography.body1,
        color = MaterialTheme.colors.secondary.copy(alpha = 0.7f),
      )
    }
  } else {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
      items(moves) {
        ChainItem(it)
      }
    }
  }
}

@Composable
internal fun ResultsList(results: List<SearchResultItem>, onResultClicked: (SearchResultItem) -> Unit) {
  val shape = RoundedCornerShape(8.dp)
  LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
    items(results) { item ->
      Row(
        modifier = Modifier
          .fillMaxWidth()
          .clip(shape)
          .background(MaterialTheme.colors.surface)
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
            style = MaterialTheme.typography.body1,
            color = MaterialTheme.colors.onSurface,
          )
          item.releaseYear?.let {
            Text(
              text = it,
              style = MaterialTheme.typography.body2,
              color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
            )
          }
        }
      }
    }
  }
}

@Composable
internal fun SearchBox(
  text: String,
  onTextInput: (String) -> Unit,
  enabled: Boolean = true,
  focusRequester: FocusRequester? = null,
  placeholder: String = "Search…",
) {
  OutlinedTextField(
    modifier = Modifier
      .fillMaxWidth()
      .then(focusRequester?.let { Modifier.focusRequester(it) } ?: Modifier),
    value = text,
    enabled = enabled,
    colors = TextFieldDefaults.outlinedTextFieldColors(
      textColor = MaterialTheme.colors.onSurface,
    ),
    placeholder = { Text(placeholder) },
    onValueChange = onTextInput,
    singleLine = true,
  )
}

@Composable
internal fun ErrorMessage(message: String, onDismiss: () -> Unit) {
  Row(
    modifier = Modifier
      .fillMaxWidth()
      .background(MaterialTheme.colors.error.copy(alpha = 0.85f), RoundedCornerShape(8.dp))
      .padding(horizontal = 12.dp, vertical = 8.dp),
    verticalAlignment = Alignment.CenterVertically
  ) {
    Text(
      text = message,
      style = MaterialTheme.typography.body2,
      color = Color.White,
      modifier = Modifier.weight(1f),
    )
    Spacer(Modifier.width(8.dp))
    Text(
      text = "Dismiss",
      style = MaterialTheme.typography.button,
      color = Color.White.copy(alpha = 0.8f),
      modifier = Modifier.clickable { onDismiss() },
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
      text = currentPlayerName.uppercase(),
      style = MaterialTheme.typography.overline,
      color = MaterialTheme.colors.secondary,
    )
    Spacer(modifier = Modifier.height(4.dp))
    Text(
      text = prompt,
      style = MaterialTheme.typography.h5,
      color = MaterialTheme.colors.primary,
    )
  }
}

@Composable
internal fun ChainItem(item: Move) {
  val label = when (item) {
    is Move.Actor -> "Actor"
    is Move.Movie -> "Movie"
  }
  val shape = RoundedCornerShape(8.dp)
  Row(
    modifier = Modifier
      .fillMaxWidth()
      .clip(shape)
      .background(MaterialTheme.colors.surface)
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
        style = MaterialTheme.typography.overline,
        color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
      )
      Text(
        text = item.displayText,
        style = MaterialTheme.typography.body1,
        color = MaterialTheme.colors.onSurface,
      )
      if (item is Move.Movie) {
        item.releaseYear?.let {
          Text(
            text = it,
            style = MaterialTheme.typography.body2,
            color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
          )
        }
      }
    }
  }
}

@Composable
internal fun TmdbAttribution(modifier: Modifier = Modifier) {
  Column(
    modifier = modifier.fillMaxWidth(),
    horizontalAlignment = Alignment.CenterHorizontally,
    verticalArrangement = Arrangement.spacedBy(4.dp)
  ) {
    // Placeholder for TMDB Logo
    Box(
      modifier = Modifier
        .size(60.dp, 20.dp)
        .background(Color(0xFF01B4E4), RoundedCornerShape(2.dp)),
      contentAlignment = Alignment.Center
    ) {
      Text(
        text = "TMDB",
        style = MaterialTheme.typography.caption,
        color = Color(0xFF0D253F),
        modifier = Modifier.padding(horizontal = 4.dp)
      )
    }
    Text(
      text = "This product uses the TMDb API but is not endorsed or certified by TMDb.",
      style = MaterialTheme.typography.caption,
      color = MaterialTheme.colors.onSurface.copy(alpha = 0.6f),
      modifier = Modifier.padding(horizontal = 16.dp),
      textAlign = androidx.compose.ui.text.style.TextAlign.Center
    )
  }
}
