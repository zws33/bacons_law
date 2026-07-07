from etl.config import BuildConfig


def extract(config: BuildConfig) -> None:
    for year in range(config.from_year, config.to_year + 1):
        print(f"printing year: {year}")
