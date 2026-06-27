package com.readlater.app.ui.screens

import android.view.View
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.readlater.app.data.model.Article

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ArticleDetailScreen(
    article: Article?,
    onBack: () -> Unit,
    onToggleRead: (Int, Boolean) -> Unit,
    onToggleFavorite: (Int, Boolean) -> Unit,
    onArchive: (Int) -> Unit,
    onDelete: (Int) -> Unit
) {
    var showMenu by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回")
                    }
                },
                actions = {
                    if (article != null) {
                        IconButton(onClick = { onToggleFavorite(article.id, !article.isFavorite) }) {
                            Icon(
                                if (article.isFavorite) Icons.Filled.Star else Icons.Outlined.StarBorder,
                                contentDescription = "收藏",
                                tint = if (article.isFavorite) Color(0xFFFF9800) else MaterialTheme.colorScheme.onSurface
                            )
                        }
                        IconButton(onClick = { onToggleRead(article.id, !article.isRead) }) {
                            Icon(
                                if (article.isRead) Icons.Filled.CheckCircle else Icons.Outlined.CheckCircleOutline,
                                contentDescription = if (article.isRead) "标为未读" else "标为已读",
                                tint = if (article.isRead) Color(0xFF4CAF50) else MaterialTheme.colorScheme.onSurface
                            )
                        }
                        IconButton(onClick = { showMenu = !showMenu }) {
                            Icon(Icons.Filled.MoreVert, "更多")
                        }
                        DropdownMenu(expanded = showMenu, onDismissRequest = { showMenu = false }) {
                            DropdownMenuItem(
                                text = { Text("归档") },
                                onClick = { onArchive(article.id); showMenu = false },
                                leadingIcon = { Icon(Icons.Outlined.Archive, null) }
                            )
                            DropdownMenuItem(
                                text = { Text("删除", color = Color.Red) },
                                onClick = { onDelete(article.id); showMenu = false },
                                leadingIcon = { Icon(Icons.Outlined.Delete, null, tint = Color.Red) }
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { padding ->
        if (article == null) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = androidx.compose.ui.Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp)
            ) {
                Text(
                    text = article.title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold
                )
                
                Spacer(Modifier.height(12.dp))
                
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    if (article.readingTime > 0) {
                        Row {
                            Icon(
                                Icons.Outlined.Schedule, null,
                                modifier = Modifier.size(16.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(Modifier.width(4.dp))
                            Text(
                                "${article.readingTime}分钟阅读",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                    if (article.wordCount > 0) {
                        Text(
                            "${article.wordCount}字",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                
                if (article.tags.isNotEmpty()) {
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        article.tags.forEach { tag ->
                            SuggestionChip(
                                onClick = { },
                                label = { Text(tag, style = MaterialTheme.typography.labelSmall) }
                            )
                        }
                    }
                }
                
                Spacer(Modifier.height(16.dp))
                HorizontalDivider()
                Spacer(Modifier.height(16.dp))
                
                // Render HTML content
                if (article.content.isNotEmpty()) {
                    ArticleWebView(article.content)
                } else {
                    Text(
                        text = article.excerpt.ifEmpty { "暂无内容" },
                        style = MaterialTheme.typography.bodyLarge
                    )
                }
                
                Spacer(Modifier.height(24.dp))
                
                if (article.url.isNotEmpty()) {
                    OutlinedButton(
                        onClick = { },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Outlined.OpenInBrowser, null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("查看原文", maxLines = 1)
                    }
                }
            }
        }
    }
}

@Composable
fun ArticleWebView(htmlContent: String) {
    val styledHtml = """
        <html><head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: -apple-system, sans-serif; font-size: 16px; line-height: 1.8; color: #333; padding: 0 8px; margin: 0; }
            img { max-width: 100%; height: auto; border-radius: 8px; }
            a { color: #2196F3; }
            blockquote { border-left: 3px solid #2196F3; padding-left: 12px; margin-left: 0; color: #666; }
            pre, code { background: #f5f5f5; border-radius: 4px; padding: 2px 6px; }
            pre { padding: 12px; overflow-x: auto; }
            h1, h2, h3 { color: #212121; }
        </style></head>
        <body>$htmlContent</body></html>
    """.trimIndent()
    
    AndroidView(
        factory = { context ->
            WebView(context).apply {
                webViewClient = WebViewClient()
                settings.javaScriptEnabled = false
                settings.defaultTextEncodingName = "UTF-8"
                loadDataWithBaseURL(null, styledHtml, "text/html", "UTF-8", null)
            }
        },
        modifier = Modifier.fillMaxWidth().wrapContentHeight()
    )
}
