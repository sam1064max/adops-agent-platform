"""Seed database from CSV files using SQLAlchemy models."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def seed_from_csv(data_dir: Path, db_url: str | None = None):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from src.models.database import Base

    url = db_url or "postgresql+psycopg2://adops:adops_secret@localhost:5432/adops_db"
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)

    csv_files = {
        "campaigns": data_dir / "campaigns.csv",
        "delivery_logs": data_dir / "delivery_logs.csv",
        "inventory": data_dir / "inventory.csv",
    }

    total = 0
    db = Session(engine)
    try:
        for table, csv_path in csv_files.items():
            if not csv_path.exists():
                logger.warning("Skipping %s: file not found", csv_path)
                continue

            df = pd.read_csv(csv_path)
            df.to_sql(table, engine, if_exists="append", index=False, method="multi")
            logger.info("Seeded %d rows into %s", len(df), table)
            total += len(df)
    except Exception as e:
        logger.error("Seed failed: %s", e)
        raise
    finally:
        db.close()

    logger.info("Seeding complete. Total records: %d", total)


def main():
    parser = argparse.ArgumentParser(description="Seed database from CSV files")
    parser.add_argument("--data-dir", type=Path, default=Path("datasets"), help="CSV directory")
    parser.add_argument("--db-url", type=str, default=None, help="SQLAlchemy DB URL")
    args = parser.parse_args()
    seed_from_csv(args.data_dir, args.db_url)


if __name__ == "__main__":
    main()
