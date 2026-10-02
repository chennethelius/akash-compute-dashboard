"""Accept provider PostgreSQL URLs using the installed psycopg 3 driver."""

from sqlalchemy.engine import make_url


def database_url(value: str):
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url
