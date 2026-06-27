package com.readlater.app.data

import android.content.Context

class Prefs(ctx: Context) {
    private val sp = ctx.getSharedPreferences("readlater", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = sp.getString("server_url", "http://192.168.31.5:8000") ?: "http://192.168.31.5:8000"
        set(v) = sp.edit().putString("server_url", v).apply()

    var fontSize: Int
        get() = sp.getInt("font_size", 17)
        set(v) = sp.edit().putInt("font_size", v).apply()

    var sortOrder: String
        get() = sp.getString("sort_order", "newest") ?: "newest"
        set(v) = sp.edit().putString("sort_order", v).apply()

    var autoArchive: Boolean
        get() = sp.getBoolean("auto_archive", false)
        set(v) = sp.edit().putBoolean("auto_archive", v).apply()

    var showImages: Boolean
        get() = sp.getBoolean("show_images", true)
        set(v) = sp.edit().putBoolean("show_images", v).apply()
}
