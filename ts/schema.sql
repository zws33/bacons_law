CREATE TABLE IF NOT EXISTS actors (
    actor_id text PRIMARY KEY,
    actor_label text NOT NULL,
    actor_sitelinks integer,
    actor_search_key text NOT NULL
);

CREATE TABLE IF NOT EXISTS movies (
    movie_id text PRIMARY KEY,
    movie_label text NOT NULL,
    movie_sitelinks integer,
    movie_year integer,
    movie_search_key text NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    movie_id text NOT NULL REFERENCES movies (movie_id),
    actor_id text NOT NULL REFERENCES actors (actor_id),
    PRIMARY KEY (movie_id, actor_id)
);
