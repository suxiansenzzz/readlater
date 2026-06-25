package com.readlater.app.util

import android.content.Context
import android.content.SharedPreferences

class PrefsManager(context: Context) {
    private val prefs: SharedPreferences = 
        context.getSharedPreferences("readlater_prefs", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString("server_url", "http://192.168.31.5:8000") ?: "http://192.168.31.5:8000"
        set(value) = prefs.edit().putString("server_url", value).apply()
}
