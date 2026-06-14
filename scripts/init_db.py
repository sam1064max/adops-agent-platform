import asyncio
import os
import sys
from pathlib import Path

import asyncpg
import pandas as pd

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://adops:adops_secret@localhost:5432/adops_db",
)

DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS campaigns (
    id              SERIAL PRIMARY KEY,
    campaign_id     VARCHAR(64) UNIQUE NOT NULL,
    name            VARCHAR(256) NOT NULL,
    channel         VARCHAR(64),
    status          VARCHAR(32) DEFAULT 'active',
    budget          NUMERIC(14,2),
    start_date      DATE,
    end_date        DATE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ad_sets (
    id              SERIAL PRIMARY KEY,
    ad_set_id       VARCHAR(64) UNIQUE NOT NULL,
    campaign_id     VARCHAR(64) REFERENCES campaigns(campaign_id),
    name            VARCHAR(256),
    targeting       JSONB,
    bid_strategy    VARCHAR(64),
    budget          NUMERIC(14,2),
    status          VARCHAR(32) DEFAULT 'active',
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS creatives (
    id              SERIAL PRIMARY KEY,
    creative_id     VARCHAR(64) UNIQUE NOT NULL,
    ad_set_id       VARCHAR(64) REFERENCES ad_sets(ad_set_id),
    title           VARCHAR(256),
    body            TEXT,
    image_url       TEXT,
    landing_url     TEXT,
    format          VARCHAR(32),
    status          VARCHAR(32) DEFAULT 'active',
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS metrics_daily (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    entity_type     VARCHAR(32) NOT NULL,
    entity_id       VARCHAR(64) NOT NULL,
    impressions     BIGINT DEFAULT 0,
    clicks          BIGINT DEFAULT 0,
    conversions     BIGINT DEFAULT 0,
    spend           NUMERIC(14,2) DEFAULT 0,
    revenue         NUMERIC(14,2) DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(date, entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS audiences (
    id              SERIAL PRIMARY KEY,
    audience_id     VARCHAR(64) UNIQUE NOT NULL,
    name            VARCHAR(256),
    size_estimate   BIGINT,
    criteria        JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id              SERIAL PRIMARY KEY,
    doc_id          VARCHAR(64) UNIQUE NOT NULL,
    title           VARCHAR(512),
    content         TEXT,
    category        VARCHAR(64),
    metadata        JSONB,
    embedding       VECTOR(1536),
    created_at      TIMESTAMP DEFAULT NOW()
);
"""


def read_csv_tables() -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    if not DATASETS_DIR.exists():
        print(f"[init_db] datasets dir not found: {DATASETS_DIR}")
        return tables

    csv_files = list(DATASETS_DIR.glob("*.csv"))
    if not csv_files:
        print("[init_db] no CSV files in datasets/")
        return tables

    for csv_file in csv_files:
        stem = csv_file.stem.lower().replace("-", "_").replace(" ", "_")
        tables[stem] = pd.read_csv(csv_file)
        print(f"[init_db] loaded {csv_file.name} -> table '{stem}' ({len(tables[stem])} rows)")

    return tables


async def seed_table(conn: asyncpg.Connection, table: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    columns = list(df.columns)
    placeholders = ", ".join(f"${i + 1}" for i in range(columns))
    col_names = ", ".join(columns)
    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    rows = [tuple(row) for _, row in df.iterrows()]
    count = 0
    for row in rows:
        try:
            await conn.execute(sql, *row)
            count += 1
        except Exception as exc:
            print(f"[init_db] skip row in {table}: {exc}")
    return count


async def main() -> None:
    print(f"[init_db] connecting to {DATABASE_URL}")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        print("[init_db] creating schema ...")
        await conn.execute(SCHEMA_SQL)
        print("[init_db] schema OK")

        csv_tables = read_csv_tables()
        for table, df in csv_tables.items():
            if table in (
                "campaigns",
                "ad_sets",
                "creatives",
                "metrics_daily",
                "audiences",
                "knowledge_base",
            ):
                n = await seed_table(conn, table, df)
                print(f"[init_db] seeded {n} rows into {table}")
            else:
                print(f"[init_db] skip unknown table '{table}'")
    finally:
        await conn.close()

    print("[init_db] done")


if __name__ == "__main__":
    asyncio.run(main())
