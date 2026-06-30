package me.zwsmith.baconslaw.ui.components

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import me.zwsmith.baconslaw.R
import me.zwsmith.baconslaw.data.MoveCandidate
import me.zwsmith.core.Move

@Composable
internal fun ChainDisplay(
  moves: List<Move>,
  modifier: Modifier = Modifier,
  contentPadding: PaddingValues = PaddingValues(0.dp),
) {
  if (moves.isEmpty()) {
    Box(modifier = modifier, contentAlignment = Alignment.Center) {
      Text(
        text = "Name an Actor to start the chain!",
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.7f),
      )
    }
  } else {
    val listState = rememberLazyListState()
    LaunchedEffect(moves.size) {
      listState.animateScrollToItem(moves.size - 1)
    }
    LazyColumn(
      state = listState,
      modifier = modifier,
      contentPadding = contentPadding,
      verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
      items(moves) { ChainItem(it) }
    }
  }
}

@Composable
internal fun MoveCandidates(
  results: List<MoveCandidate>,
  onResultClicked: (MoveCandidate) -> Unit,
  modifier: Modifier = Modifier,
) {
  LazyColumn(
    modifier = modifier,
    verticalArrangement = Arrangement.spacedBy(8.dp),
  ) {
    items(results) { item ->
      MoveCandidateItem(onResultClicked, item)
    }
  }
}

@Composable
private fun MoveCandidateItem(
  onResultClicked: (MoveCandidate) -> Unit,
  item: MoveCandidate
) {
  val shape = RoundedCornerShape(8.dp)
  Row(
    modifier = Modifier
      .fillMaxWidth()
      .clip(shape)
      .background(MaterialTheme.colorScheme.surface)
      .clickable { onResultClicked(item) }
      .padding(8.dp),
    verticalAlignment = Alignment.CenterVertically
  ) {
    when (item) {
      is MoveCandidate.Actor -> {
        AsyncImage(
          model = item.imageUrl,
          contentDescription = null,
          modifier = Modifier
            .size(48.dp)
            .clip(RoundedCornerShape(4.dp))
            .background(Color.Gray),
          contentScale = ContentScale.Crop,
        )
        Spacer(Modifier.width(12.dp))
        Text(
          text = item.displayText,
          style = MaterialTheme.typography.bodyLarge,
          color = MaterialTheme.colorScheme.onSurface,
        )
      }

      is MoveCandidate.Movie -> {
        Column {
          Text(
            text = item.displayText,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
          )
          item.releaseYear?.let {
            Text(
              text = it,
              style = MaterialTheme.typography.bodySmall,
              color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
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
  modifier: Modifier = Modifier,
  enabled: Boolean = true,
  focusRequester: FocusRequester? = null,
  placeholder: String = "Type an actor or movie…",
) {
  OutlinedTextField(
    modifier = modifier
      .fillMaxWidth()
      .then(focusRequester?.let { Modifier.focusRequester(it) } ?: Modifier),
    value = text,
    enabled = enabled,
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
      .background(MaterialTheme.colorScheme.error.copy(alpha = 0.85f), RoundedCornerShape(8.dp))
      .padding(horizontal = 12.dp, vertical = 8.dp),
    verticalAlignment = Alignment.CenterVertically
  ) {
    Text(
      text = message,
      style = MaterialTheme.typography.bodyLarge,
      color = Color.White,
      modifier = Modifier.weight(1f),
    )
    Spacer(Modifier.width(8.dp))
    Text(
      text = "Dismiss",
      style = MaterialTheme.typography.labelMedium,
      color = Color.White.copy(alpha = 0.8f),
      modifier = Modifier.clickable { onDismiss() },
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
      .background(MaterialTheme.colorScheme.surface)
      .padding(8.dp),
    verticalAlignment = Alignment.CenterVertically
  ) {
    Column(
      horizontalAlignment = Alignment.Start,
      verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
      Text(
        text = label,
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
      )
      Text(
        text = item.displayText,
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurface,
      )
      if (item is Move.Movie) {
        item.releaseYear?.let {
          Text(
            text = it,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
          )
        }
      }
    }
  }
}

@Composable
internal fun TmdbAttribution(modifier: Modifier = Modifier) {
  Row(
    modifier = modifier.fillMaxWidth(),
    horizontalArrangement = Arrangement.spacedBy(4.dp),
    verticalAlignment = Alignment.CenterVertically,
  ) {
    Image(
      modifier = Modifier.size(64.dp, 24.dp),
      painter = painterResource(R.drawable.tmdb_logo),
      contentDescription = null
    )
    Text(
      text = "This product uses the TMDb API but is not endorsed or certified by TMDb.",
      style = MaterialTheme.typography.bodySmall,
      color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
      modifier = Modifier.padding(horizontal = 16.dp),
      textAlign = TextAlign.Start
    )
  }
}
