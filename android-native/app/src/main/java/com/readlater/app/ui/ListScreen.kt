package com.readlater.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
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
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.readlater.app.data.Article
import com.readlater.app.viewmodel.ListState

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

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        // iOS-style large title header
        Column(Modifier.padding(start = 20.dp, end = 20.dp, top = 16.dp, bottom = 4.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("稍后阅读", fontSize = 32.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onBackground)
                IconButton(onClick = onSettings, modifier = Modifier.size(40.dp)) {
                    Icon(Icons.Filled.Settings, "设置", tint = iOSGray4, modifier = Modifier.size(22.dp))
                }
            }
        }

        // iOS-style filter pills
        Row(Modifier.padding(horizontal = 20.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            filters.forEach { (key, label) ->
                val selected = state.filter == key
                Surface(
                    onClick = { onFilter(key) },
                    shape = RoundedCornerShape(20.dp),
                    color = if (selected) iOSBlue else Color.White,
                    shadowElevation = if (selected) 0.dp else 1.dp
                ) {
                    Text(
                        label,
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 7.dp),
                        fontSize = 13.sp,
                        fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
                        color = if (selected) Color.White else iOSGray5
                    )
                }
            }
        }

        // Content
        Box(Modifier.fillMaxSize()) {
            when {
                state.error != null && state.articles.isEmpty() -> {
                    Column(Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        Icon(Icons.Filled.CloudOff, null, Modifier.size(56.dp), tint = iOSGray3)
                        Spacer(Modifier.height(12.dp))
                        Text("连接失败", fontSize = 17.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onBackground)
                        Spacer(Modifier.height(4.dp))
                        Text(state.error, fontSize = 14.sp, color = iOSGray4)
                        Spacer(Modifier.height(20.dp))
                        Button(onClick = onRefresh, shape = RoundedCornerShape(12.dp), colors = ButtonDefaults.buttonColors(containerColor = iOSBlue)) {
                            Text("重试")
                        }
                    }
                }
                !state.loading && state.articles.isEmpty() -> {
                    Column(Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        Icon(Icons.Filled.Article, null, Modifier.size(56.dp), tint = iOSGray3)
                        Spacer(Modifier.height(12.dp))
                        Text("还没有文章", fontSize = 17.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onBackground)
                        Spacer(Modifier.height(4.dp))
                        Text("点击右下角按钮保存文章", fontSize = 14.sp, color = iOSGray4)
                    }
                }
                else -> {
                    LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        items(state.articles, key = { it.id }) { a ->
                            ArticleCard(a) { onClick(a) }
                        }
                        if (state.page < state.totalPages) {
                            item {
                                LaunchedEffect(Unit) { onMore() }
                                Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                                    CircularProgressIndicator(Modifier.size(24.dp), color = iOSBlue, strokeWidth = 2.dp)
                                }
                            }
                        }
                    }
                }
            }

            // iOS-style FAB
            FloatingActionButton(
                onClick = onAdd,
                modifier = Modifier.align(Alignment.BottomEnd).padding(20.dp).size(56.dp),
                shape = CircleShape,
                containerColor = iOSBlue,
                contentColor = Color.White,
                elevation = FloatingActionButtonDefaults.elevation(4.dp)
            ) {
                Icon(Icons.Filled.Add, "添加", modifier = Modifier.size(26.dp))
            }
        }
    }
}

@Composable
fun ArticleCard(article: Article, onClick: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(14.dp),
        color = Color.White,
        shadowElevation = 1.dp
    ) {
        Column {
            if (article.lead_image_url.isNotEmpty()) {
                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current).data(article.lead_image_url).crossfade(true).build(),
                    contentDescription = null,
                    modifier = Modifier.fillMaxWidth().height(170.dp).clip(RoundedCornerShape(topStart = 14.dp, topEnd = 14.dp)),
                    contentScale = ContentScale.Crop
                )
            }
            Column(Modifier.padding(14.dp)) {
                Text(article.title, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis, color = Color(0xFF1C1C1E))
                if (article.excerpt.isNotEmpty()) {
                    Spacer(Modifier.height(5.dp))
                    Text(article.excerpt, fontSize = 14.sp, color = iOSGray4, maxLines = 2, overflow = TextOverflow.Ellipsis, lineHeight = 20.sp)
                }
                Spacer(Modifier.height(10.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (article.reading_time > 0) {
                            Icon(Icons.Filled.Schedule, null, Modifier.size(13.dp), tint = iOSGray3)
                            Spacer(Modifier.width(3.dp))
                            Text("${article.reading_time}分钟", fontSize = 12.sp, color = iOSGray4)
                            Spacer(Modifier.width(10.dp))
                        }
                        if (article.word_count > 0) {
                            Text("${article.word_count}字", fontSize = 12.sp, color = iOSGray4)
                        }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (article.is_favorite) Icon(Icons.Filled.Star, null, Modifier.size(16.dp), tint = iOSOrange)
                        if (article.is_read) { Spacer(Modifier.width(5.dp)); Icon(Icons.Filled.CheckCircle, null, Modifier.size(16.dp), tint = iOSGreen) }
                    }
                }
            }
        }
    }
}
