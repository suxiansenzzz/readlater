package com.readlater.app.ui

import androidx.compose.runtime.*
import androidx.lifecycle.viewmodel.compose.viewModel
import com.readlater.app.viewmodel.VM

sealed class Screen {
    data object List : Screen()
    data class Detail(val id: Int) : Screen()
    data object Settings : Screen()
}

@Composable
fun ReadLaterApp(vm: VM = viewModel()) {
    var screen by remember { mutableStateOf<Screen>(Screen.List) }
    var showAdd by remember { mutableStateOf(false) }

    val listState by vm.list.collectAsState()
    val selArticle by vm.article.collectAsState()
    val msg by vm.msg.collectAsState()

    LaunchedEffect(Unit) { vm.load() }

    val snackbar = remember { androidx.compose.material3.SnackbarHostState() }
    LaunchedEffect(msg) {
        msg?.let { snackbar.showSnackbar(it); vm.clearMsg() }
    }

    when (screen) {
        is Screen.List -> ListScreen(
            state = listState,
            onRefresh = { vm.load() },
            onClick = { a -> vm.loadArticle(a.id); screen = Screen.Detail(a.id) },
            onFilter = { f -> vm.load(filter = f) },
            onMore = { vm.load(page = listState.page + 1) },
            onAdd = { showAdd = true },
            onSettings = { screen = Screen.Settings }
        )
        is Screen.Detail -> DetailScreen(
            article = selArticle,
            fontSize = vm.prefs.fontSize,
            onBack = { vm.clearArticle(); screen = Screen.List },
            onFav = { id, f -> vm.update(id, fav = f) },
            onRead = { id, r -> vm.update(id, read = r) },
            onArchive = { id -> vm.update(id, arch = true) },
            onDelete = { id -> vm.delete(id) }
        )
        is Screen.Settings -> SettingsScreen(
            url = vm.serverUrl,
            fontSize = vm.prefs.fontSize,
            sortOrder = vm.prefs.sortOrder,
            autoArchive = vm.prefs.autoArchive,
            showImages = vm.prefs.showImages,
            onSave = { u -> vm.setServer(u); screen = Screen.List },
            onFontSize = { s -> vm.setFontSize(s) },
            onSortOrder = { o -> vm.setSortOrder(o) },
            onAutoArchive = { v -> vm.setAutoArchive(v) },
            onShowImages = { v -> vm.setShowImages(v) },
            onBack = { screen = Screen.List }
        )
    }

    if (showAdd) {
        AddDialog(onDismiss = { showAdd = false }, onSave = { u, t -> vm.save(u, t); showAdd = false })
    }
}
