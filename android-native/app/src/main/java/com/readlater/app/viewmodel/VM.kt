package com.readlater.app.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.readlater.app.data.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class ListState(
    val articles: List<Article> = emptyList(),
    val loading: Boolean = false,
    val error: String? = null,
    val page: Int = 1,
    val totalPages: Int = 1,
    val filter: String = "all"
)

class VM(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)
    private fun api() = Client.get(prefs.serverUrl)

    private val _list = MutableStateFlow(ListState())
    val list: StateFlow<ListState> = _list

    private val _article = MutableStateFlow<Article?>(null)
    val article: StateFlow<Article?> = _article

    private val _msg = MutableStateFlow<String?>(null)
    val msg: StateFlow<String?> = _msg

    val serverUrl get() = prefs.serverUrl

    fun load(page: Int = 1, filter: String = _list.value.filter) {
        _list.value = _list.value.copy(loading = true, error = null, filter = filter)
        viewModelScope.launch {
            try {
                val r = api().getArticles(
                    page = page,
                    isRead = when (filter) { "unread" -> false; "read" -> true; else -> null },
                    isFavorite = if (filter == "favorite") true else null,
                    isArchived = if (filter == "archived") true else null
                )
                _list.value = _list.value.copy(
                    articles = if (page == 1) r.articles else _list.value.articles + r.articles,
                    loading = false, page = r.page, totalPages = r.total_pages
                )
            } catch (e: Exception) {
                _list.value = _list.value.copy(loading = false, error = e.message ?: "加载失败")
            }
        }
    }

    fun loadArticle(id: Int) {
        viewModelScope.launch {
            try { _article.value = api().getArticle(id) }
            catch (_: Exception) { _article.value = null }
        }
    }

    fun save(url: String, title: String? = null) {
        viewModelScope.launch {
            try {
                val r = api().saveArticle(SaveReq(url, title))
                _msg.value = if (r.success) "保存成功！" else (r.message ?: "保存失败")
                if (r.success) load()
            } catch (e: Exception) { _msg.value = "失败: ${e.message}" }
        }
    }

    fun update(id: Int, read: Boolean? = null, fav: Boolean? = null, arch: Boolean? = null) {
        viewModelScope.launch {
            try {
                api().updateArticle(id, UpdateReq(read, fav, arch))
                load()
                if (_article.value?.id == id) loadArticle(id)
            } catch (_: Exception) {}
        }
    }

    fun delete(id: Int) {
        viewModelScope.launch {
            try { api().deleteArticle(id); load(); _article.value = null }
            catch (_: Exception) {}
        }
    }

    fun clearMsg() { _msg.value = null }
    fun clearArticle() { _article.value = null }

    fun setServer(url: String) { prefs.serverUrl = url; load() }
    fun setFontSize(size: Int) { prefs.fontSize = size }
    fun setSortOrder(order: String) { prefs.sortOrder = order }
    fun setAutoArchive(v: Boolean) { prefs.autoArchive = v }
    fun setShowImages(v: Boolean) { prefs.showImages = v }
}
