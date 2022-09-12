package com.zwsmith.bacons_law.data

data class MovieSearchResponse(
    val page: Int,
    val results: List<Result>,
    val total_pages: Int,
    val total_results: Int
) {
    data class Result(
        val genre_ids: List<Int>,
        val id: Int,
        val overview: String,
        val popularity: Double,
        val poster_path: String,
        val release_date: String,
        val title: String,
    )
}
