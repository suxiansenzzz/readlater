package com.readlater.app.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.readlater.app.data.api.RetrofitClient
import com.readlater.app.data.model.Article
import com.readlater.app.data.model.Stats
import com.readlater.app.util.PrefsManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class ArticleListState(
    val articles: List<Article> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val currentPage: Int = 1,
    val totalPages: Int = 1,
    val filter: String = "all" // all, unread, favorite, archived
)

data class StatsState(
    val stats: Stats? = null,
    val isLoading: Boolean = false
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val prefs = PrefsManager(application)
    
    private val _listState = MutableStateFlow(ArticleListState())
    val listState: StateFlow<ArticleListState> = _listState
    
    private val _statsState = MutableStateFlow(StatsState())
    val statsState: StateFlow<StatsState> = _statsState
    
    private val _selectedArticle = MutableStateFlow<Article?>(null)
    val selectedArticle: StateFlow<Article?> = _selectedArticle
    
    private val _saveResult = MutableStateFlow<String?>(null)
    val saveResult: StateFlow<String?> = _saveResult

    val serverUrl: String get() = prefs.serverUrl

    private fun api() = RetrofitClient.getApi(prefs.serverUrl)

    fun loadArticles(page: Int = 1, filter: String = _listState.value.filter) {
        _listState.value = _listState.value.copy(isLoading = true, error = null, filter = filter)
        viewModelScope.launch {
            try {
                val isRead = when (filter) { "unread" -> false; "read" -> true; else -> null }
                val isFavorite = if (filter == "favorite") true else null
                val isArchived = if (filter == "archived") true else null
                
                val response = api().getArticles(
                    page = page, perPage = 20,
                    isRead = isRead, isFavorite = isFavorite, isArchived = isArchived
                )
                _listState.value = _listState.value.copy(
                    articles = if (page == 1) response.articles else _listState.value.articles + response.articles,
                    isLoading = false,
                    currentPage = response.page,
                    totalPages = response.totalPages
                )
            } catch (e: Exception) {
                _listState.value = _listState.value.copy(
                    isLoading = false,
                    error = e.message ?: "加载失败"
                )
            }
        }
    }

    fun loadArticle(id: Int) {
        viewModelScope.launch {
            try {
                val article = api().getArticle(id)
                _selectedArticle.value = article
            } catch (e: Exception) {
                _selectedArticle.value = null
            }
        }
    }

    fun loadStats() {
        _statsState.value = _statsState.value.copy(isLoading = true)
        viewModelScope.launch {
            try {
                val stats = api().getStats()
                _statsState.value = StatsState(stats = stats, isLoading = false)
            } catch (e: Exception) {
                _statsState.value = StatsState(isLoading = false)
            }
        }
    }

    fun saveArticle(url: String, title: String? = null) {
        viewModelScope.launch {
            try {
                val request = com.readlater.app.data.model.ArticleCreateRequest(url = url, title = title)
                val response = api().saveArticle(request)
                _saveResult.value = if (response.success) "保存成功！" else (response.message ?: "保存失败")
                if (response.success) loadArticles()
            } catch (e: Exception) {
                _saveResult.value = "保存失败: ${e.message}"
            }
        }
    }

    fun updateArticle(id: Int, isRead: Boolean? = null, isFavorite: Boolean? = null, isArchived: Boolean? = null) {
        viewModelScope.launch {
            try {
                val request = com.readlater.app.data.model.ArticleUpdateRequest(
                    isRead = isRead, isFavorite = isFavorite, isArchived = isArchived
                )
                api().updateArticle(id, request)
                // Refresh
                loadArticles()
                if (_selectedArticle.value?.id == id) {
                    loadArticle(id)
                }
            } catch (_: Exception) {}
        }
    }

    fun deleteArticle(id: Int) {
        viewModelScope.launch {
            try {
                api().deleteArticle(id)
                loadArticles()
                _selectedArticle.value = null
            } catch (_: Exception) {}
        }
    }

    fun clearSaveResult() { _saveResult.value = null }
    fun clearSelectedArticle() { _selectedArticle.value = null }
    
    fun updateServerUrl(url: String) {
        prefs.serverUrl = url
        RetrofitClient.reset()
    }
}
