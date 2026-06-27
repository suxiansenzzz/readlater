package com.readlater.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun SettingsScreen(url: String, onSave: (String) -> Unit, onBack: () -> Unit) {
    var text by remember { mutableStateOf(url) }

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        // Nav bar
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回", tint = iOSBlue, modifier = Modifier.size(24.dp)) }
            Text("设置", fontSize = 17.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onBackground)
        }

        Spacer(Modifier.height(8.dp))

        // Server URL card
        Surface(Modifier.fillMaxWidth().padding(horizontal = 16.dp), shape = RoundedCornerShape(14.dp), color = Color.White, shadowElevation = 1.dp) {
            Column(Modifier.padding(16.dp)) {
                Text("服务器地址", fontSize = 13.sp, color = iOSGray4, fontWeight = FontWeight.Medium)
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = text, onValueChange = { text = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("http://192.168.31.5:8000", fontSize = 15.sp) },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = iOSBlue, unfocusedBorderColor = iOSGray2)
                )
                Spacer(Modifier.height(12.dp))
                Button(
                    onClick = { onSave(text) },
                    modifier = Modifier.fillMaxWidth().height(44.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = iOSBlue)
                ) { Text("保存", fontSize = 16.sp, fontWeight = FontWeight.SemiBold) }
            }
        }

        Spacer(Modifier.height(24.dp))

        // App info
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("ReadLater", fontSize = 13.sp, color = iOSGray3)
            Text("v2.2.0", fontSize = 12.sp, color = iOSGray3)
        }
    }
}
