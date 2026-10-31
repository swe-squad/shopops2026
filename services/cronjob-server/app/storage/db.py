"""Each operation owns its connection and transaction."""

import psycopg
from psycopg.rows import dict_row

from app.config import Settings


def connect(settings: Settings | None = None) -> psycopg.Connection:
    return psycopg.connect(
        **(settings or Settings.from_env()).connection_kwargs(), row_factory=dict_row
    )
