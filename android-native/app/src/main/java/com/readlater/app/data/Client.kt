package com.readlater.app.data

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit

object Client {
    private var api: ApiService? = null
    private var url: String? = null

    fun get(serverUrl: String): ApiService {
        val norm = serverUrl.trimEnd('/') + "/"
        if (api == null || url != norm) {
            url = norm
            val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
            val client = OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .build()
            api = Retrofit.Builder()
                .baseUrl(norm)
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create(moshi))
                .build()
                .create(ApiService::class.java)
        }
        return api!!
    }
}
