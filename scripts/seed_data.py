"""Script to seed database from CSV files."""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def seed_campaigns(csv_path: Path, db_connection) -> int:
    """Seed campaign data from CSV file."""
    if not csv_path.exists():
        logger.warning("CSV file not found: %s", csv_path)
        return 0

    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                db_connection.execute(
                    """
                    INSERT OR REPLACE INTO campaigns
                    (id, name, status, budget, start_date, end_date, platform)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["name"],
                        row.get("status", "active"),
                        float(row.get("budget", 0)),
                        row.get("start_date", ""),
                        row.get("end_date", ""),
                        row.get("platform", ""),
                    ),
                )
                count += 1
            except Exception as e:
                logger.error("Failed to seed campaign %s: %s", row.get("id"), e)

    logger.info("Seeded %d campaigns from %s", count, csv_path)
    return count


def seed_keywords(csv_path: Path, db_connection) -> int:
    """Seed keyword data from CSV file."""
    if not csv_path.exists():
        logger.warning("CSV file not found: %s", csv_path)
        return 0

    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                db_connection.execute(
                    """
                    INSERT OR REPLACE INTO keywords
                    (id, campaign_id, keyword, match_type, bid, impressions, clicks, cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["campaign_id"],
                        row["keyword"],
                        row.get("match_type", "broad"),
                        float(row.get("bid", 0)),
                        int(row.get("impressions", 0)),
                        int(row.get("clicks", 0)),
                        float(row.get("cost", 0)),
                    ),
                )
                count += 1
            except Exception as e:
                logger.error("Failed to seed keyword %s: %s", row.get("id"), e)

    logger.info("Seeded %d keywords from %s", count, csv_path)
    return count


def seed_performance(csv_path: Path, db_connection) -> int:
    """Seed daily performance data from CSV file."""
    if not csv_path.exists():
        logger.warning("CSV file not found: %s", csv_path)
        return 0

    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                db_connection.execute(
                    """
                    INSERT OR REPLACE INTO daily_performance
                    (campaign_id, date, impressions, clicks, cost, conversions, revenue)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["campaign_id"],
                        row["date"],
                        int(row.get("impressions", 0)),
                        int(row.get("clicks", 0)),
                        float(row.get("cost", 0)),
                        int(row.get("conversions", 0)),
                        float(row.get("revenue", 0)),
                    ),
                )
                count += 1
            except Exception as e:
                logger.error("Failed to seed performance row: %s", e)

    logger.info("Seeded %d performance rows from %s", count, csv_path)
    return count


def main():
    parser = argparse.ArgumentParser(description="Seed database from CSV files")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing CSV files",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("adops.db"),
        help="SQLite database path",
    )
    args = parser.parse_args()

    import sqlite3

    db = sqlite3.connect(args.db_path)

    db.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            budget REAL DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            platform TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            match_type TEXT DEFAULT 'broad',
            bid REAL DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            cost REAL DEFAULT 0,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS daily_performance (
            campaign_id TEXT NOT NULL,
            date TEXT NOT NULL,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            cost REAL DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            PRIMARY KEY (campaign_id, date),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        )
    """)

    logger.info("Database tables created at %s", args.db_path)

    total = 0
    total += seed_campaigns(args.data_dir / "campaigns.csv", db)
    total += seed_keywords(args.data_dir / "keywords.csv", db)
    total += seed_performance(args.data_dir / "performance.csv", db)

    db.commit()
    db.close()

    logger.info("Seeding complete. Total records: %d", total)


if __name__ == "__main__":
    main()
