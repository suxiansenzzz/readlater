package com.readlater.app.ui

import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.readlater.app.data.Article

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailScreen(
    article: Article?,
    onBack: () -> Unit,
    onFav: (Int, Boolean) -> Unit,
    onRead: (Int, Boolean) -> Unit,
    onArchive: (Int) -> Unit,
    onDelete: (Int) -> Unit
) {
    var menu by remember { mutableStateOf(false) }

    Scaffold(topBar = {
        TopAppBar(
            title = { },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") } },
            actions = {
                if (article != null) {
                    IconButton(onClick = { onFav(article.id, !article.is_favorite) }) {
                        Icon(if (article.is_favorite) Icons.Filled.Star else Icons.Outlined.StarBorder, "收藏",
                            tint = if (article.is_favorite) Color(0xFFFF9800) else MaterialTheme.colorScheme.onSurface)
                    }
                    IconButton(onClick = { onRead(article.id, !article.is_read) }) {
                        Icon(if (article.is_read) Icons.Filled.CheckCircle else Icons.Outlined.CheckCircleOutline, "已读",
                            tint = if (article.is_read) Color(0xFF4CAF50) else MaterialTheme.colorScheme.onSurface)
                    }
                    IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, "更多") }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        DropdownMenuItem(text = { Text("归档") }, onClick = { onArchive(article.id); menu = false }, leadingIcon = { Icon(Icons.Outlined.Archive, null) })
                        DropdownMenuItem(text = { Text("删除", color = Color.Red) }, onClick = { onDelete(article.id); menu = false }, leadingIcon = { Icon(Icons.Outlined.Delete, null, tint = Color.Red) })
                    }
                }
            }
        )
    }) { pad ->
        if (article == null) {
            Box(Modifier.fillMaxSize().padding(pad)) { CircularProgressIndicator(Modifier.padding(32.dp)) }
        } else {
            Column(Modifier.fillMaxSize().padding(pad).verticalScroll(rememberScrollState()).padding(16.dp)) {
                Text(article.title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    if (article.reading_time > 0) Text("${article.reading_time}分钟阅读", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (article.word_count > 0) Text("${article.word_count}字", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(16.dp))
                HorizontalDivider()
                Spacer(Modifier.height(16.dp))
                if (article.content.isNotEmpty()) {
                    val html = """<html><head><meta name="viewport" content="width=device-width,initial-scale=1.0">
                        <style>body{font-family:sans-serif;font-size:16px;line-height:1.8;color:#333;padding:0 8px;margin:0}
                        img{max-width:100%;height:auto;border-radius:8px}a{color:#2196F3}
                        blockquote{border-left:3px solid #2196F3;padding-left:12px;margin-left:0;color:#666}
                        pre,code{background:#f5f5f5;border-radius:4px;padding:2px 6px}pre{padding:12px;overflow-x:auto}</style></head>
                        <body>${article.content}</body></html>"""
                    AndroidView(factory = { ctx -> WebView(ctx).apply {
                        webViewClient = WebViewClient(); settings.javaScriptEnabled = false
                        loadDataWithBaseURL(null, html, "text/html", "UTF-8", null)
                    }}, modifier = Modifier.fillMaxWidth().wrapContentHeight())
                } else {
                    Text(article.excerpt.ifEmpty { "暂无内容" }, style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
    }
}
