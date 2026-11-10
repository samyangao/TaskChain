"""PostgreSQL connection helper."""

import os
import psycopg
from psycopg.rows import dict_row


def db():
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "ias_auth_demo"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        row_factory=dict_row,
    )
