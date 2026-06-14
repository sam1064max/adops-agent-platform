"""Data loader for sample datasets and PostgreSQL seeding."""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class DataLoader:
    """Loads sample datasets and seeds PostgreSQL databases."""

    def load_campaigns(self, csv_path: str) -> pd.DataFrame:
        """Load campaign data from CSV.

        Args:
            csv_path: Path to the campaigns CSV file.

        Returns:
            DataFrame with campaign data.

        Raises:
            FileNotFoundError: If CSV file does not exist.
            ValueError: If CSV is empty or malformed.
        """
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Campaigns CSV not found: {csv_path}"
            )

        try:
            df = pd.read_csv(csv_path)
            if df.empty:
                logger.warning("Campaigns CSV is empty: %s", csv_path)
            else:
                logger.info(
                    "Loaded %d campaign records from %s",
                    len(df),
                    csv_path,
                )
            return df
        except Exception as exc:
            raise ValueError(
                f"Failed to parse campaigns CSV: {exc}"
            ) from exc

    def load_delivery_logs(self, csv_path: str) -> pd.DataFrame:
        """Load delivery log data from CSV.

        Args:
            csv_path: Path to the delivery logs CSV file.

        Returns:
            DataFrame with delivery log data.

        Raises:
            FileNotFoundError: If CSV file does not exist.
            ValueError: If CSV is empty or malformed.
        """
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Delivery logs CSV not found: {csv_path}"
            )

        try:
            df = pd.read_csv(csv_path)
            if df.empty:
                logger.warning(
                    "Delivery logs CSV is empty: %s", csv_path
                )
            else:
                logger.info(
                    "Loaded %d delivery log records from %s",
                    len(df),
                    csv_path,
                )
            return df
        except Exception as exc:
            raise ValueError(
                f"Failed to parse delivery logs CSV: {exc}"
            ) from exc

    def load_inventory(self, csv_path: str) -> pd.DataFrame:
        """Load inventory data from CSV.

        Args:
            csv_path: Path to the inventory CSV file.

        Returns:
            DataFrame with inventory data.

        Raises:
            FileNotFoundError: If CSV file does not exist.
            ValueError: If CSV is empty or malformed.
        """
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Inventory CSV not found: {csv_path}"
            )

        try:
            df = pd.read_csv(csv_path)
            if df.empty:
                logger.warning(
                    "Inventory CSV is empty: %s", csv_path
                )
            else:
                logger.info(
                    "Loaded %d inventory records from %s",
                    len(df),
                    csv_path,
                )
            return df
        except Exception as exc:
            raise ValueError(
                f"Failed to parse inventory CSV: {exc}"
            ) from exc

    def seed_database(
        self,
        engine: Engine,
        campaigns_df: Optional[pd.DataFrame] = None,
        delivery_df: Optional[pd.DataFrame] = None,
        inventory_df: Optional[pd.DataFrame] = None,
    ) -> dict:
        """Seed the PostgreSQL database with DataFrames.

        Args:
            engine: SQLAlchemy engine instance.
            campaigns_df: Campaign data to insert.
            delivery_df: Delivery log data to insert.
            inventory_df: Inventory data to insert.

        Returns:
            Dictionary with table names as keys and row counts as values.
        """
        results = {}

        tables = {
            "campaigns": campaigns_df,
            "delivery_logs": delivery_df,
            "inventory": inventory_df,
        }

        for table_name, df in tables.items():
            if df is None or df.empty:
                logger.info(
                    "Skipping table '%s' (no data)", table_name
                )
                continue

            try:
                rows_inserted = df.to_sql(
                    name=table_name,
                    con=engine,
                    if_exists="append",
                    index=False,
                    chunksize=500,
                )
                # pandas.to_sql returns None when chunksize is set
                # Fall back to row count from DataFrame
                count = len(df) if rows_inserted is None else rows_inserted
                results[table_name] = count
                logger.info(
                    "Seeded %d rows into '%s'", count, table_name
                )
            except Exception:
                logger.exception(
                    "Failed to seed table '%s'", table_name
                )
                results[table_name] = 0

        total = sum(results.values())
        logger.info(
            "Database seeding complete. Total rows inserted: %d", total
        )
        return results
