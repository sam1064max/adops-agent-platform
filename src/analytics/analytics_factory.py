"""Analytics factory providing singleton access to all analyzer instances."""

from typing import Optional

from .auction_analyzer import AuctionAnalyzer
from .ctr_analyzer import CTRAnalyzer
from .fill_rate_analyzer import FillRateAnalyzer
from .inventory_analyzer import InventoryAnalyzer
from .pacing_analyzer import PacingAnalyzer


class AnalyticsFactory:
    """Singleton factory that provides cached analyzer instances.

    Usage:
        factory = AnalyticsFactory()
        ctr = factory.get_ctr_analyzer()
        pacing = factory.get_pacing_analyzer()
    """

    _instance: Optional["AnalyticsFactory"] = None

    def __new__(cls) -> "AnalyticsFactory":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._fill_rate_analyzer: Optional[FillRateAnalyzer] = None
        self._ctr_analyzer: Optional[CTRAnalyzer] = None
        self._pacing_analyzer: Optional[PacingAnalyzer] = None
        self._inventory_analyzer: Optional[InventoryAnalyzer] = None
        self._auction_analyzer: Optional[AuctionAnalyzer] = None

    def get_fill_rate_analyzer(self) -> FillRateAnalyzer:
        """Return a cached FillRateAnalyzer instance."""
        if self._fill_rate_analyzer is None:
            self._fill_rate_analyzer = FillRateAnalyzer()
        return self._fill_rate_analyzer

    def get_ctr_analyzer(self) -> CTRAnalyzer:
        """Return a cached CTRAnalyzer instance."""
        if self._ctr_analyzer is None:
            self._ctr_analyzer = CTRAnalyzer()
        return self._ctr_analyzer

    def get_pacing_analyzer(self) -> PacingAnalyzer:
        """Return a cached PacingAnalyzer instance."""
        if self._pacing_analyzer is None:
            self._pacing_analyzer = PacingAnalyzer()
        return self._pacing_analyzer

    def get_inventory_analyzer(self) -> InventoryAnalyzer:
        """Return a cached InventoryAnalyzer instance."""
        if self._inventory_analyzer is None:
            self._inventory_analyzer = InventoryAnalyzer()
        return self._inventory_analyzer

    def get_auction_analyzer(self) -> AuctionAnalyzer:
        """Return a cached AuctionAnalyzer instance."""
        if self._auction_analyzer is None:
            self._auction_analyzer = AuctionAnalyzer()
        return self._auction_analyzer
