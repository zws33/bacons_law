from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MovieSearchResult(_CamelModel):
    id: int
    title: str
    release_year: str | None = None
    poster_path: str | None = None


class PersonSearchResult(_CamelModel):
    id: int
    name: str
    profile_path: str | None = None


class MovieCreditsResult(_CamelModel):
    id: int
    cast_ids: list[int]
