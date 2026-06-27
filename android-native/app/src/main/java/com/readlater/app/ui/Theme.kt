package com.readlater.app.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

val iOSBlue = Color(0xFF007AFF)
val iOSGreen = Color(0xFF34C759)
val iOSOrange = Color(0xFFFF9500)
val iOSRed = Color(0xFFFF3B30)
val iOSGray1 = Color(0xFFF2F2F7)
val iOSGray2 = Color(0xFFE5E5EA)
val iOSGray3 = Color(0xFFC7C7CC)
val iOSGray4 = Color(0xFF8E8E93)
val iOSGray5 = Color(0xFF636366)
val iOSGray6 = Color(0xFF3A3A3C)

// Theme-aware card color
val LocalCardColor = staticCompositionLocalOf { Color.White }
val LocalCardText = staticCompositionLocalOf { Color(0xFF1C1C1E) }
val LocalSubText = staticCompositionLocalOf { Color(0xFF8E8E93) }

private val Light = lightColorScheme(
    primary = iOSBlue, onPrimary = Color.White,
    background = iOSGray1, surface = Color.White,
    onBackground = Color(0xFF1C1C1E), onSurface = Color(0xFF1C1C1E),
    surfaceVariant = Color.White, outline = iOSGray2,
    onSurfaceVariant = iOSGray4, error = iOSRed
)

private val Dark = darkColorScheme(
    primary = Color(0xFF0A84FF), onPrimary = Color.White,
    background = Color(0xFF000000), surface = iOSGray6,
    onBackground = Color(0xFFE5E5EA), onSurface = Color(0xFFE5E5EA),
    surfaceVariant = iOSGray6, outline = Color(0xFF38383A),
    onSurfaceVariant = iOSGray4, error = Color(0xFFFF453A)
)

@Composable
fun AppTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val colors = if (dark) Dark else Light
    CompositionLocalProvider(
        LocalCardColor provides if (dark) iOSGray6 else Color.White,
        LocalCardText provides if (dark) Color(0xFFE5E5EA) else Color(0xFF1C1C1E),
        LocalSubText provides if (dark) iOSGray4 else iOSGray4
    ) {
        MaterialTheme(colorScheme = colors, content = content)
    }
}
