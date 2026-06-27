package com.readlater.app.data

import android.content.Context

class Prefs(ctx: Context) {
    private val sp = ctx.getSharedPreferences("readlater", Context.MODE_PRIVATE)
    var serverUrl: String
        get() = sp.getString("server_url", "http://192.168.31.5:8000") ?: "http://192.168.31.5:8000"
        set(v) = sp.edit().putString("server_url", v).apply()
}
