package com.zwsmith.bacons_law.data

import com.zwsmith.bacons_law.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface Api {
    @GET("search/movie?api_key=${BuildConfig.ApiKey}")
    suspend fun searchMovies(
        @Query("query") query: String
    ): MovieSearchResponse

    @GET("search/person?api_key=${BuildConfig.ApiKey}")
    suspend fun searchActor(
        @Query("query") query: String
    ): ActorSearchResponse

    @GET("movie/{movieId}/credits?api_key=${BuildConfig.ApiKey}")
    suspend fun getCredits(
        @Path("movieId") movieId: Int
    ): CreditsResponse

    companion object {
        private const val BASE_URL = "https://api.themoviedb.org/3/"

        fun create(): Api {
            val logger = HttpLoggingInterceptor().apply {
                level =
                    HttpLoggingInterceptor.Level.BASIC
            }

            val client = OkHttpClient.Builder()
                .addInterceptor(logger)
                .build()

            return Retrofit.Builder()
                .baseUrl(BASE_URL)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(Api::class.java)
        }
    }
}