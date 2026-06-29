from app.util import CamelModel


class MovieSearchResult(CamelModel):
    id: int
    title: str
    release_year: str | None = None
    poster_path: str | None = None


class PersonSearchResult(CamelModel):
    id: int
    name: str
    profile_path: str | None = None


class MovieCreditsResult(CamelModel):
    id: int
    cast_ids: list[int]
