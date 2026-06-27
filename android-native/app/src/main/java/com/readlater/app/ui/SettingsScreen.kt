package com.readlater.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Sort
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun SettingsScreen(
    url: String,
    fontSize: Int,
    sortOrder: String,
    autoArchive: Boolean,
    showImages: Boolean,
    onSave: (String) -> Unit,
    onFontSize: (Int) -> Unit,
    onSortOrder: (String) -> Unit,
    onAutoArchive: (Boolean) -> Unit,
    onShowImages: (Boolean) -> Unit,
    onBack: () -> Unit
) {
    var text by remember { mutableStateOf(url) }

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).verticalScroll(rememberScrollState())) {
        // Nav bar
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回", tint = iOSBlue, modifier = Modifier.size(24.dp)) }
            Text("设置", fontSize = 17.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onBackground)
        }

        Spacer(Modifier.height(4.dp))

        // Section: Server
        SectionHeader("服务器")
        SettingsCard {
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

        Spacer(Modifier.height(20.dp))

        // Section: Reading
        SectionHeader("阅读")
        SettingsCard {
            Column {
                // Font size
                SettingsRow(icon = Icons.Filled.TextFields, title = "正文字号") {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        listOf(14 to "小", 17 to "中", 20 to "大", 24 to "特大").forEach { (size, label) ->
                            val selected = fontSize == size
                            Surface(
                                onClick = { onFontSize(size) },
                                shape = RoundedCornerShape(8.dp),
                                color = if (selected) iOSBlue else Color.Transparent
                            ) {
                                Text(label, modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                                    fontSize = 13.sp, fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                                    color = if (selected) Color.White else iOSGray5)
                            }
                            Spacer(Modifier.width(6.dp))
                        }
                    }
                }

                HorizontalDivider(color = iOSGray2, thickness = 0.5.dp, modifier = Modifier.padding(horizontal = 16.dp))

                // Sort order
                SettingsRow(icon = Icons.AutoMirrored.Filled.Sort, title = "默认排序") {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        listOf("newest" to "最新", "oldest" to "最早").forEach { (key, label) ->
                            val selected = sortOrder == key
                            Surface(
                                onClick = { onSortOrder(key) },
                                shape = RoundedCornerShape(8.dp),
                                color = if (selected) iOSBlue else Color.Transparent
                            ) {
                                Text(label, modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                                    fontSize = 13.sp, fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                                    color = if (selected) Color.White else iOSGray5)
                            }
                            Spacer(Modifier.width(6.dp))
                        }
                    }
                }

                HorizontalDivider(color = iOSGray2, thickness = 0.5.dp, modifier = Modifier.padding(horizontal = 16.dp))

                // Show images
                SettingsSwitchRow(icon = Icons.Filled.Image, title = "显示封面图", checked = showImages, onToggle = onShowImages)

                HorizontalDivider(color = iOSGray2, thickness = 0.5.dp, modifier = Modifier.padding(horizontal = 16.dp))

                // Auto archive
                SettingsSwitchRow(icon = Icons.Filled.Archive, title = "已读自动归档", checked = autoArchive, onToggle = onAutoArchive)
            }
        }

        Spacer(Modifier.height(20.dp))

        // Section: About
        SectionHeader("关于")
        SettingsCard {
            Column(Modifier.padding(16.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("版本", fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface)
                    Text("v2.2.2", fontSize = 15.sp, color = iOSGray4)
                }
                Spacer(Modifier.height(8.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("开发者", fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface)
                    Text("心怡", fontSize = 15.sp, color = iOSGray4)
                }
            }
        }

        Spacer(Modifier.height(32.dp))
    }
}

@Composable
fun SectionHeader(title: String) {
    Text(title.uppercase(), fontSize = 13.sp, fontWeight = FontWeight.Medium, color = iOSGray4,
        modifier = Modifier.padding(start = 20.dp, top = 8.dp, bottom = 6.dp))
}

@Composable
fun SettingsCard(content: @Composable () -> Unit) {
    Surface(Modifier.fillMaxWidth().padding(horizontal = 16.dp), shape = RoundedCornerShape(14.dp), color = Color.White, shadowElevation = 1.dp) {
        content()
    }
}

@Composable
fun SettingsRow(icon: ImageVector, title: String, trailing: @Composable () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, modifier = Modifier.size(20.dp), tint = iOSBlue)
        Spacer(Modifier.width(12.dp))
        Text(title, fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(1f))
        trailing()
    }
}

@Composable
fun SettingsSwitchRow(icon: ImageVector, title: String, checked: Boolean, onToggle: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, modifier = Modifier.size(20.dp), tint = iOSBlue)
        Spacer(Modifier.width(12.dp))
        Text(title, fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onToggle, colors = SwitchDefaults.colors(checkedTrackColor = iOSBlue))
    }
}
