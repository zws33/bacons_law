"""BuildConfig rejects dial combinations that can only produce an empty artifact.

These fire at construction rather than three stages later, because zero edges from a bad
range is indistinguishable from a legitimately empty catalog by the time emit sees it.
"""

from collections.abc import Callable

import pytest

from etl.config import BuildConfig


def test_defaults_are_valid():
    cfg = BuildConfig()
    assert cfg.year_from <= cfg.year_to
    assert cfg.cast_cap >= cfg.min_cast


def test_inverted_year_range_is_rejected():
    with pytest.raises(ValueError, match="year_from"):
        BuildConfig(year_from=2020, year_to=1990)


def test_single_year_range_is_allowed():
    """from == to is a one-partition pull, not an error — used to resume a single year."""
    assert BuildConfig(year_from=1994, year_to=1994).year_from == 1994


@pytest.mark.parametrize(
    ("build", "match"),
    [
        (lambda: BuildConfig(cast_cap=0), "cast_cap"),
        (lambda: BuildConfig(cast_cap=-1), "cast_cap"),
        (lambda: BuildConfig(min_cast=0), "min_cast"),
        (lambda: BuildConfig(min_sitelinks=-1), "min_sitelinks"),
    ],
)
def test_nonsense_dials_are_rejected(build: Callable[[], BuildConfig], match: str):
    """Factories rather than a **kwargs dict: splatting dict[str, int] into a dataclass
    with bool and str fields is untypeable, and these must stay checkable."""
    with pytest.raises(ValueError, match=match):
        build()


def test_cap_below_min_cast_is_permitted():
    """Independent knobs: min_cast gates on the FULL cast, cast_cap limits emitted degree.
    A film can pass the gate and still emit fewer edges. Odd, but intentional — see
    transform._build_edge_list — so it is not a construction error."""
    assert BuildConfig(min_cast=5, cast_cap=2).cast_cap == 2
