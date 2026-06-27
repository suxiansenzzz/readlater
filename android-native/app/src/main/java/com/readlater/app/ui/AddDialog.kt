package com.readlater.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun AddDialog(onDismiss: () -> Unit, onSave: (String, String?) -> Unit) {
    var url by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }

    AlertDialog(onDismissRequest = onDismiss,
        title = { Text("保存文章") },
        text = {
            Column {
                OutlinedTextField(value = url, onValueChange = { url = it }, modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("粘贴链接...") }, singleLine = true, label = { Text("URL") })
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = title, onValueChange = { title = it }, modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("可选标题") }, singleLine = true, label = { Text("标题") })
            }
        },
        confirmButton = { Button(onClick = { onSave(url, title.ifBlank { null }) }, enabled = url.isNotBlank()) { Text("保存") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } }
    )
}
