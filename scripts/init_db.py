"""Initialize database schema and seed sample data."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import settings
from src.models.database import Campaign, DeliveryLog, InventoryMetadata, Base, SessionLocal, engine, init_db
from src.ingestion.data_loader import DataLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"


def seed_from_csv():
    logger.info("Creating tables...")
    init_db()

    loader = DataLoader()

    campaigns_file = DATASETS_DIR / "campaigns.csv"
    delivery_file = DATASETS_DIR / "delivery_logs.csv"
    inventory_file = DATASETS_DIR / "inventory.csv"

    db = SessionLocal()
    try:
        if campaigns_file.exists():
            campaigns_df = loader.load_campaigns(str(campaigns_file))
            n = loader.seed_database(engine, campaigns_df, None, None)
            logger.info("Seeded campaigns data")
        else:
            logger.warning("Campaigns CSV not found: %s", campaigns_file)

        if delivery_file.exists():
            delivery_df = loader.load_delivery_logs(str(delivery_file))
            loader.seed_database(engine, None, delivery_df, None)
            logger.info("Seeded delivery logs")

        if inventory_file.exists():
            inventory_df = loader.load_inventory(str(inventory_file))
            loader.seed_database(engine, None, None, inventory_df)
            logger.info("Seeded inventory metadata")

        logger.info("Database initialization complete")
    except Exception as e:
        logger.error("Failed to seed database: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_from_csv()
