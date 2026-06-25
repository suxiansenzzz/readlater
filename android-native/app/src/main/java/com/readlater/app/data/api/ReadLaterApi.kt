package com.readlater.app.data.api

import com.readlater.app.data.model.*
import retrofit2.Response
import retrofit2.http.*

interface ReadLaterApi {

    @GET("api/articles")
    suspend fun getArticles(
        @Query("page") page: Int = 1,
        @Query("per_page") perPage: Int = 20,
        @Query("is_read") isRead: Boolean? = null,
        @Query("is_favorite") isFavorite: Boolean? = null,
        @Query("is_archived") isArchived: Boolean? = null,
        @Query("tag") tag: String? = null,
        @Query("search") search: String? = null,
        @Query("sort") sort: String = "created_at",
        @Query("order") order: String = "desc"
    ): ArticleListResponse

    @GET("api/articles/{id}")
    suspend fun getArticle(@Path("id") articleId: Int): Article

    @POST("api/save")
    suspend fun saveArticle(@Body request: ArticleCreateRequest): SaveResponse

    @PUT("api/articles/{id}")
    suspend fun updateArticle(
        @Path("id") articleId: Int,
        @Body request: ArticleUpdateRequest
    ): UpdateResponse

    @DELETE("api/articles/{id}")
    suspend fun deleteArticle(@Path("id") articleId: Int): DeleteResponse

    @GET("api/stats")
    suspend fun getStats(): Stats
}
