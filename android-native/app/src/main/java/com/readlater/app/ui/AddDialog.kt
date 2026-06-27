package com.readlater.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun AddDialog(onDismiss: () -> Unit, onSave: (String, String?) -> Unit) {
    var url by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("保存文章", fontSize = 17.sp, fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold) },
        text = {
            Column {
                OutlinedTextField(
                    value = url, onValueChange = { url = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("粘贴链接...") },
                    singleLine = true,
                    label = { Text("URL") },
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = iOSBlue, unfocusedBorderColor = iOSGray2)
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = title, onValueChange = { title = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("可选标题") },
                    singleLine = true,
                    label = { Text("标题") },
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = iOSBlue, unfocusedBorderColor = iOSGray2)
                )
            }
        },
        confirmButton = {
            Button(onClick = { onSave(url, title.ifBlank { null }) }, enabled = url.isNotBlank(),
                shape = RoundedCornerShape(10.dp), colors = ButtonDefaults.buttonColors(containerColor = iOSBlue)) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消", color = iOSGray4) } },
        shape = RoundedCornerShape(16.dp)
    )
}
