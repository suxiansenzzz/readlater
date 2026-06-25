package com.readlater.app

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import com.readlater.app.ui.screens.*
import com.readlater.app.ui.theme.ReadLaterTheme
import com.readlater.app.viewmodel.MainViewModel

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ReadLaterTheme {
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

    // Load on first composition
    LaunchedEffect(Unit) {
        viewModel.loadArticles()
    }

    // Show save result as snackbar
    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(saveResult) {
        saveResult?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearSaveResult()
        }
    }

    when (val screen = currentScreen) {
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

    // Add article dialog
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
