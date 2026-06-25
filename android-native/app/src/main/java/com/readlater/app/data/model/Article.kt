package com.readlater.app.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class Article(
    val id: Int,
    val url: String,
    val title: String,
    val content: String = "",
    val excerpt: String = "",
    val tags: List<String> = emptyList(),
    @Json(name = "is_read") val isRead: Boolean = false,
    @Json(name = "is_favorite") val isFavorite: Boolean = false,
    @Json(name = "is_archived") val isArchived: Boolean = false,
    @Json(name = "created_at") val createdAt: String = "",
    @Json(name = "word_count") val wordCount: Int = 0,
    @Json(name = "reading_time") val readingTime: Int = 0,
    @Json(name = "lead_image_url") val leadImageUrl: String = ""
)

@JsonClass(generateAdapter = true)
data class ArticleListResponse(
    val articles: List<Article>,
    val total: Int,
    val page: Int,
    @Json(name = "per_page") val perPage: Int,
    @Json(name = "total_pages") val totalPages: Int
)

@JsonClass(generateAdapter = true)
data class ArticleCreateRequest(
    val url: String,
    val title: String? = null,
    val tags: List<String>? = null
)

@JsonClass(generateAdapter = true)
data class ArticleUpdateRequest(
    val title: String? = null,
    val tags: List<String>? = null,
    @Json(name = "is_read") val isRead: Boolean? = null,
    @Json(name = "is_favorite") val isFavorite: Boolean? = null,
    @Json(name = "is_archived") val isArchived: Boolean? = null
)

@JsonClass(generateAdapter = true)
data class Stats(
    val total: Int = 0,
    val read: Int = 0,
    val unread: Int = 0,
    val favorites: Int = 0,
    val archived: Int = 0,
    @Json(name = "this_week") val thisWeek: Int = 0
)

@JsonClass(generateAdapter = true)
data class SaveResponse(
    val success: Boolean,
    val message: String? = null,
    @Json(name = "article_id") val articleId: Int? = null,
    @Json(name = "images_pending") val imagesPending: Boolean? = null
)

@JsonClass(generateAdapter = true)
data class UpdateResponse(
    val success: Boolean
)

@JsonClass(generateAdapter = true)
data class DeleteResponse(
    val success: Boolean
)

@JsonClass(generateAdapter = true)
data class ErrorResponse(
    val detail: String? = null,
    val error: String? = null
)
