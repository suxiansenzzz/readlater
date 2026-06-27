package com.readlater.app.ui

import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.readlater.app.data.Article

@Composable
fun DetailScreen(
    article: Article?,
    fontSize: Int = 17,
    onBack: () -> Unit,
    onFav: (Int, Boolean) -> Unit,
    onRead: (Int, Boolean) -> Unit,
    onArchive: (Int) -> Unit,
    onDelete: (Int) -> Unit
) {
    var menu by remember { mutableStateOf(false) }

    Column(Modifier.fillMaxSize().background(Color.White)) {
        // Nav bar
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回", tint = iOSBlue, modifier = Modifier.size(24.dp)) }
            Row {
                if (article != null) {
                    IconButton(onClick = { onFav(article.id, !article.is_favorite) }) {
                        Icon(if (article.is_favorite) Icons.Filled.Star else Icons.Outlined.StarBorder, "收藏",
                            tint = if (article.is_favorite) iOSOrange else iOSGray3, modifier = Modifier.size(22.dp))
                    }
                    IconButton(onClick = { onRead(article.id, !article.is_read) }) {
                        Icon(if (article.is_read) Icons.Filled.CheckCircle else Icons.Outlined.CheckCircleOutline, "已读",
                            tint = if (article.is_read) iOSGreen else iOSGray3, modifier = Modifier.size(22.dp))
                    }
                    IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, "更多", tint = iOSGray4, modifier = Modifier.size(22.dp)) }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        DropdownMenuItem(text = { Text("归档") }, onClick = { onArchive(article.id); menu = false }, leadingIcon = { Icon(Icons.Outlined.Archive, null) })
                        DropdownMenuItem(text = { Text("删除", color = iOSRed) }, onClick = { onDelete(article.id); menu = false }, leadingIcon = { Icon(Icons.Outlined.Delete, null, tint = iOSRed) })
                    }
                }
            }
        }

        if (article == null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = iOSBlue, strokeWidth = 2.dp) }
        } else {
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)) {
                Text(article.title, fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF1C1C1E), lineHeight = 28.sp)
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    if (article.reading_time > 0) Text("${article.reading_time}分钟阅读", fontSize = 13.sp, color = iOSGray4)
                    if (article.word_count > 0) Text("${article.word_count}字", fontSize = 13.sp, color = iOSGray4)
                }
                Spacer(Modifier.height(16.dp))
                HorizontalDivider(color = iOSGray2, thickness = 0.5.dp)
                Spacer(Modifier.height(16.dp))
                val content = article.content
                if (!content.isNullOrEmpty()) {
                    val html = "<html><head><meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\">" +
                        "<style>body{font-family:-apple-system,sans-serif;font-size:${fontSize}px;line-height:1.7;color:#1C1C1E;padding:0;margin:0}" +
                        "img{max-width:100%;height:auto;border-radius:8px}a{color:#007AFF}" +
                        "blockquote{border-left:3px solid #007AFF;padding-left:12px;margin-left:0;color:#636366}" +
                        "pre,code{background:#F2F2F7;border-radius:6px;padding:2px 6px;font-size:${fontSize - 2}px}pre{padding:12px;overflow-x:auto}" +
                        "h1,h2,h3{color:#1C1C1E}</style></head>" +
                        "<body>$content</body></html>"
                    AndroidView(factory = { ctx -> WebView(ctx).apply {
                        webViewClient = WebViewClient(); settings.javaScriptEnabled = false
                        loadDataWithBaseURL(null, html, "text/html", "UTF-8", null)
                    }}, modifier = Modifier.fillMaxWidth().wrapContentHeight())
                } else {
                    Text(article.excerpt ?: "暂无内容", fontSize = fontSize.sp, color = Color(0xFF1C1C1E), lineHeight = (fontSize + 10).sp)
                }
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}
