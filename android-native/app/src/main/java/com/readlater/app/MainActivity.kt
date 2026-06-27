package com.readlater.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.viewmodel.compose.viewModel
import com.readlater.app.ui.screens.*
import com.readlater.app.viewmodel.MainViewModel

// Colors defined directly in Compose - no XML theme needed
private val LightColors = lightColorScheme(
    primary = Color(0xFF2196F3),
    onPrimary = Color.White,
    primaryContainer = Color(0xFF90CAF9),
    secondary = Color(0xFF03DAC5),
    background = Color(0xFFFAFAFA),
    surface = Color.White,
    onBackground = Color(0xFF212121),
    onSurface = Color(0xFF212121),
    surfaceVariant = Color(0xFFF5F5F5),
    outline = Color(0xFFE0E0E0)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF90CAF9),
    onPrimary = Color(0xFF212121),
    primaryContainer = Color(0xFF1976D2),
    secondary = Color(0xFF03DAC5),
    background = Color(0xFF121212),
    surface = Color(0xFF1E1E1E),
    onBackground = Color(0xFFF5F5F5),
    onSurface = Color(0xFFF5F5F5),
    surfaceVariant = Color(0xFF2C2C2C),
    outline = Color(0xFF757575)
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val colors = if (isSystemInDarkTheme()) DarkColors else LightColors
            MaterialTheme(colorScheme = colors) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    ReadLaterApp()
                }
            }
        }
    }
}

sealed class Screen {
    data object List : Screen()
    data class Detail(val articleId: Int) : Screen()
    data object Settings : Screen()
}

@Composable
fun ReadLaterApp(viewModel: MainViewModel = viewModel()) {
    var currentScreen by remember { mutableStateOf<Screen>(Screen.List) }
    var showAddDialog by remember { mutableStateOf(false) }
    
    val listState by viewModel.listState.collectAsState()
    val selectedArticle by viewModel.selectedArticle.collectAsState()
    val saveResult by viewModel.saveResult.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadArticles()
    }

    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(saveResult) {
        saveResult?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearSaveResult()
        }
    }

    when (currentScreen) {
        is Screen.List -> {
            ArticleListScreen(
                state = listState,
                onRefresh = { viewModel.loadArticles() },
                onArticleClick = { article ->
                    viewModel.loadArticle(article.id)
                    currentScreen = Screen.Detail(article.id)
                },
                onFilterChange = { filter -> viewModel.loadArticles(filter = filter) },
                onLoadMore = { viewModel.loadArticles(page = listState.currentPage + 1) },
                onAddClick = { showAddDialog = true }
            )
        }
        is Screen.Detail -> {
            ArticleDetailScreen(
                article = selectedArticle,
                onBack = {
                    viewModel.clearSelectedArticle()
                    currentScreen = Screen.List
                },
                onToggleRead = { id, isRead -> viewModel.updateArticle(id, isRead = isRead) },
                onToggleFavorite = { id, isFav -> viewModel.updateArticle(id, isFavorite = isFav) },
                onArchive = { id -> viewModel.updateArticle(id, isArchived = true) },
                onDelete = { id -> viewModel.deleteArticle(id) }
            )
        }
        is Screen.Settings -> {
            SettingsScreen(
                currentUrl = viewModel.serverUrl,
                onSave = { url ->
                    viewModel.updateServerUrl(url)
                    viewModel.loadArticles()
                    currentScreen = Screen.List
                },
                onBack = { currentScreen = Screen.List }
            )
        }
    }

    if (showAddDialog) {
        AddArticleDialog(
            onDismiss = { showAddDialog = false },
            onSave = { url, title ->
                viewModel.saveArticle(url, title)
                showAddDialog = false
            }
        )
    }
}
