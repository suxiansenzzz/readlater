package com.readlater.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.readlater.app.data.Article
import com.readlater.app.viewmodel.ListState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ListScreen(
    state: ListState,
    onRefresh: () -> Unit,
    onClick: (Article) -> Unit,
    onFilter: (String) -> Unit,
    onMore: () -> Unit,
    onAdd: () -> Unit,
    onSettings: () -> Unit
) {
    val filters = listOf("all" to "全部", "unread" to "未读", "favorite" to "收藏", "archived" to "已归档")

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("稍后阅读", fontWeight = FontWeight.Bold) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary
                ),
                actions = {
                    IconButton(onClick = onSettings) {
                        Icon(Icons.Filled.Settings, "设置", tint = MaterialTheme.colorScheme.onPrimary)
                    }
                }
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onAdd, containerColor = MaterialTheme.colorScheme.primary) {
                Icon(Icons.Filled.Add, "添加", tint = MaterialTheme.colorScheme.onPrimary)
            }
        }
    ) { pad ->
        Column(Modifier.padding(pad)) {
            ScrollableTabRow(
                selectedTabIndex = filters.indexOfFirst { it.first == state.filter }.coerceAtLeast(0),
                containerColor = MaterialTheme.colorScheme.surface,
                edgePadding = 16.dp
            ) {
                filters.forEach { (k, label) ->
                    Tab(selected = state.filter == k, onClick = { onFilter(k) },
                        text = { Text(label, fontWeight = if (state.filter == k) FontWeight.Bold else FontWeight.Normal) })
                }
            }
            Box(Modifier.fillMaxSize()) {
                when {
                    state.error != null && state.articles.isEmpty() -> {
                        Column(Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                            Icon(Icons.Filled.CloudOff, null, Modifier.size(64.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(0.5f))
                            Spacer(Modifier.height(16.dp))
                            Text("连接失败")
                            Spacer(Modifier.height(8.dp))
                            Text(state.error, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Spacer(Modifier.height(24.dp))
                            Button(onClick = onRefresh) { Text("重试") }
                        }
                    }
                    !state.loading && state.articles.isEmpty() -> {
                        Column(Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                            Icon(Icons.AutoMirrored.Filled.Article, null, Modifier.size(64.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(0.5f))
                            Spacer(Modifier.height(16.dp))
                            Text("还没有文章")
                            Spacer(Modifier.height(8.dp))
                            Text("点击右下角按钮保存", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    else -> {
                        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            items(state.articles, key = { it.id }) { a ->
                                Card(Modifier.fillMaxWidth().clickable { onClick(a) }, shape = RoundedCornerShape(12.dp),
                                    elevation = CardDefaults.cardElevation(2.dp)) {
                                    Column {
                                        if (a.lead_image_url.isNotEmpty()) {
                                            AsyncImage(model = ImageRequest.Builder(LocalContext.current).data(a.lead_image_url).crossfade(true).build(),
                                                contentDescription = null, modifier = Modifier.fillMaxWidth().height(160.dp).clip(RoundedCornerShape(topStart = 12.dp, topEnd = 12.dp)),
                                                contentScale = ContentScale.Crop)
                                        }
                                        Column(Modifier.padding(14.dp)) {
                                            Text(a.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                            if (a.excerpt.isNotEmpty()) {
                                                Spacer(Modifier.height(6.dp))
                                                Text(a.excerpt, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
                                            }
                                            Spacer(Modifier.height(8.dp))
                                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                                Row(verticalAlignment = Alignment.CenterVertically) {
                                                    if (a.reading_time > 0) Text("${a.reading_time}分钟", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                                    if (a.word_count > 0) { Spacer(Modifier.width(8.dp)); Text("${a.word_count}字", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                                                }
                                                Row {
                                                    if (a.is_favorite) Icon(Icons.Filled.Star, null, Modifier.size(16.dp), tint = Color(0xFFFF9800))
                                                    if (a.is_read) { Spacer(Modifier.width(4.dp)); Icon(Icons.Filled.CheckCircle, null, Modifier.size(16.dp), tint = Color(0xFF4CAF50)) }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            if (state.page < state.totalPages) {
                                item { LaunchedEffect(Unit) { onMore() }; Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator(Modifier.size(24.dp)) } }
                            }
                        }
                    }
                }
            }
        }
    }
}
