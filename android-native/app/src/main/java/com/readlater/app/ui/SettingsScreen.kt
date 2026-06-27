package com.readlater.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(url: String, onSave: (String) -> Unit, onBack: () -> Unit) {
    var text by remember { mutableStateOf(url) }

    Scaffold(topBar = {
        TopAppBar(title = { Text("设置") },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") } })
    }) { pad ->
        Column(Modifier.fillMaxSize().padding(pad).padding(16.dp)) {
            Text("服务器地址", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(value = text, onValueChange = { text = it }, modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("http://192.168.31.5:8000") }, singleLine = true)
            Spacer(Modifier.height(16.dp))
            Button(onClick = { onSave(text) }, modifier = Modifier.fillMaxWidth()) { Text("保存") }
            Spacer(Modifier.height(16.dp))
            Text("ReadLater v2.2.0", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
