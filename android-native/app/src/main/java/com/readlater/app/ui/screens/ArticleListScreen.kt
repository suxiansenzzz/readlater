package com.readlater.app.ui.screens

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Article
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*

import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.readlater.app.data.model.Article
import com.readlater.app.viewmodel.ArticleListState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ArticleListScreen(
    state: ArticleListState,
    onRefresh: () -> Unit,
    onArticleClick: (Article) -> Unit,
    onFilterChange: (String) -> Unit,
    onLoadMore: () -> Unit,
    onAddClick: () -> Unit
) {
    val filters = listOf("all" to "全部", "unread" to "未读", "favorite" to "收藏", "archived" to "已归档")

    Scaffold(
        topBar = {
            TopAppBar(
                title = { 
                    Text("稍后阅读", fontWeight = FontWeight.Bold) 
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    actionIconContentColor = MaterialTheme.colorScheme.onPrimary
                ),
                actions = {
                    IconButton(onClick = onAddClick) {
                        Icon(Icons.Filled.Add, "添加文章")
                    }
                }
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onAddClick,
                containerColor = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary
            ) {
                Icon(Icons.Filled.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("保存文章")
            }
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding)) {
            // Filter chips
            ScrollableTabRow(
                selectedTabIndex = filters.indexOfFirst { it.first == state.filter }.coerceAtLeast(0),
                containerColor = MaterialTheme.colorScheme.surface,
                edgePadding = 16.dp,
                divider = {}
            ) {
                filters.forEach { (key, label) ->
                    Tab(
                        selected = state.filter == key,
                        onClick = { onFilterChange(key) },
                        text = {
                            Text(
                                label,
                                fontWeight = if (state.filter == key) FontWeight.Bold else FontWeight.Normal
                            )
                        }
                    )
                }
            }

            // Content
            Box(modifier = Modifier.fillMaxSize()) {
                if (state.error != null && state.articles.isEmpty()) {
                    ErrorState(state.error) { onRefresh() }
                } else if (!state.isLoading && state.articles.isEmpty()) {
                    EmptyState(state.filter)
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        items(state.articles, key = { it.id }) { article ->
                            ArticleCard(
                                article = article,
                                onClick = { onArticleClick(article) }
                            )
                        }
                        if (state.currentPage < state.totalPages) {
                            item {
                                LaunchedEffect(Unit) { onLoadMore() }
                                Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                                    CircularProgressIndicator(modifier = Modifier.size(24.dp))
                                }
                            }
                        }
                    }
                    // Loading indicator overlay
                    if (state.isLoading && state.articles.isNotEmpty()) {
                        CircularProgressIndicator(
                            modifier = Modifier.align(Alignment.TopCenter).padding(16.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun ArticleCard(article: Article, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column {
            // Hero image
            if (article.leadImageUrl.isNotEmpty()) {
                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current)
                        .data(article.leadImageUrl)
                        .crossfade(true)
                        .build(),
                    contentDescription = article.title,
                    modifier = Modifier.fillMaxWidth().height(180.dp)
                        .clip(RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp)),
                    contentScale = ContentScale.Crop
                )
            }
            
            Column(modifier = Modifier.padding(16.dp)) {
                // Title
                Text(
                    text = article.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                
                if (article.excerpt.isNotEmpty()) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        text = article.excerpt,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 3,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                
                Spacer(Modifier.height(10.dp))
                
                // Metadata row
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (article.readingTime > 0) {
                            Icon(
                                Icons.Outlined.Schedule, 
                                contentDescription = null,
                                modifier = Modifier.size(14.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(Modifier.width(4.dp))
                            Text(
                                "${article.readingTime}分钟",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(Modifier.width(12.dp))
                        }
                        if (article.wordCount > 0) {
                            Text(
                                "${article.wordCount}字",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                    
                    Row {
                        if (article.isFavorite) {
                            Icon(
                                Icons.Filled.Star,
                                contentDescription = "收藏",
                                modifier = Modifier.size(16.dp),
                                tint = Color(0xFFFF9800)
                            )
                            Spacer(Modifier.width(6.dp))
                        }
                        if (article.isRead) {
                            Icon(
                                Icons.Filled.CheckCircle,
                                contentDescription = "已读",
                                modifier = Modifier.size(16.dp),
                                tint = Color(0xFF4CAF50)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ErrorState(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Filled.CloudOff,
            contentDescription = null,
            modifier = Modifier.size(64.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
        )
        Spacer(Modifier.height(16.dp))
        Text("连接失败", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        Text(
            message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.height(24.dp))
        Button(onClick = onRetry) { Text("重试") }
    }
}

@Composable
fun EmptyState(filter: String) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.AutoMirrored.Outlined.Article,
            contentDescription = null,
            modifier = Modifier.size(64.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
        )
        Spacer(Modifier.height(16.dp))
        Text(
            when (filter) {
                "unread" -> "没有未读文章"
                "favorite" -> "没有收藏文章"
                "archived" -> "没有归档文章"
                else -> "还没有文章"
            },
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(Modifier.height(8.dp))
        Text(
            "点击右下角按钮保存文章",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
