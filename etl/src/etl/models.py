from dataclasses import dataclass, field


@dataclass(frozen=True)
class Actor:
    qid: str
    label: str
    sitelinks: int


@dataclass
class Film:
    qid: str
    label: str
    sitelinks: int
    # actor_qid -> Actor. A dict so duplicate rows across year partitions collapse for free.
    cast: dict[str, Actor] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    movie: str
    movie_label: str
    actor: str
    actor_label: str
