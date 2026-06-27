package com.readlater.app.data

import retrofit2.http.*
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class Article(
    val id: Int = 0,
    val title: String = "",
    val url: String = "",
    val excerpt: String = "",
    val content: String = "",
    val lead_image_url: String = "",
    val word_count: Int = 0,
    val reading_time: Int = 0,
    val is_read: Boolean = false,
    val is_favorite: Boolean = false,
    val is_archived: Boolean = false,
    val tags: List<String> = emptyList(),
    val created_at: String = ""
)

@JsonClass(generateAdapter = true)
data class ArticleListResp(
    val articles: List<Article> = emptyList(),
    val page: Int = 1,
    val total_pages: Int = 1
)

@JsonClass(generateAdapter = true)
data class SaveResp(val success: Boolean = false, val message: String? = null)

@JsonClass(generateAdapter = true)
data class SaveReq(val url: String, val title: String? = null)

@JsonClass(generateAdapter = true)
data class UpdateReq(
    val is_read: Boolean? = null,
    val is_favorite: Boolean? = null,
    val is_archived: Boolean? = null
)

interface ApiService {
    @GET("api/articles")
    suspend fun getArticles(
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 20,
        @Query("is_read") isRead: Boolean? = null,
        @Query("is_favorite") isFavorite: Boolean? = null,
        @Query("is_archived") isArchived: Boolean? = null,
        @Query("search") search: String? = null
    ): ArticleListResp

    @GET("api/articles/{id}")
    suspend fun getArticle(@Path("id") id: Int): Article

    @POST("api/save")
    suspend fun saveArticle(@Body req: SaveReq): SaveResp

    @PUT("api/articles/{id}")
    suspend fun updateArticle(@Path("id") id: Int, @Body req: UpdateReq)

    @DELETE("api/articles/{id}")
    suspend fun deleteArticle(@Path("id") id: Int)
}
