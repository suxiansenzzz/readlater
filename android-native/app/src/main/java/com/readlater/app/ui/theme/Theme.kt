package com.readlater.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = Blue500,
    onPrimary = CardBackground,
    primaryContainer = Blue200,
    secondary = Teal200,
    background = Surface,
    surface = CardBackground,
    onBackground = Gray900,
    onSurface = Gray900,
    surfaceVariant = Gray100,
    outline = Gray300
)

private val DarkColorScheme = darkColorScheme(
    primary = Blue200,
    onPrimary = Gray900,
    primaryContainer = Blue700,
    secondary = Teal200,
    background = Gray900,
    surface = Color(0xFF1E1E1E),
    onBackground = Gray100,
    onSurface = Gray100,
    surfaceVariant = Color(0xFF2C2C2C),
    outline = Gray600
)

@Composable
fun ReadLaterTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography(),
        content = content
    )
}
