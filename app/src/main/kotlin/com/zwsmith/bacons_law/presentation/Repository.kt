package com.zwsmith.bacons_law.presentation

import com.zwsmith.bacons_law.data.Api
import timber.log.Timber

@Suppress("FunctionName")
fun Repository(): RepositoryImpl {
    return RepositoryImpl(Api.create())
}

interface Repository {

    suspend fun searchMovies(query: String): List<Movie>
    suspend fun searchActors(query: String): List<Actor>
}

class RepositoryImpl(val api: Api) : Repository {
    override suspend fun searchActors(query: String): List<Actor> {
        return try {
            api.searchActor(query).results.map { Actor(it.id, it.name) }
        } catch (e: Throwable) {
            Timber.e(e)
            emptyList()
        }
    }

    override suspend fun searchMovies(query: String): List<Movie> {
        return try {
            api.searchMovies(query).results.map { Movie(it.id, it.title) }
        } catch (e: Throwable) {
            Timber.e(e)
            emptyList()
        }
    }

    suspend fun getCastByMovieId(movieId: Int): List<Actor> {
        return try {
            api.getCredits(movieId).cast.map { Actor(it.id, it.name) }
        } catch (e: Throwable) {
            Timber.e(e)
            emptyList()
        }
    }
}