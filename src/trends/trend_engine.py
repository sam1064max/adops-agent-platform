"""Trend analysis engine for ad delivery metrics with forecasting and anomaly detection."""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from sklearn.linear_model import LinearRegression
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


class TrendEngine:
    """Computes trends, anomalies, seasonality, and forecasts for delivery metrics."""

    @staticmethod
    def compute_7day_trend(
        df: pd.DataFrame,
        metric: str,
    ) -> Dict[str, Any]:
        """Compute short-term (7-day) trend direction and volatility.

        Expects df with a datetime column named 'timestamp' or 'date'.

        Args:
            df: DataFrame with time-series data.
            metric: Column name of the metric to analyze.

        Returns:
            Dict with direction ('up', 'down', 'stable'), change_pct, volatility.
        """
        series = TrendEngine._extract_series(df, metric)
        if len(series) < 2:
            return {"direction": "stable", "change_pct": 0.0, "volatility": 0.0}

        window = min(7, len(series))
        recent = series[-window:]
        earlier = series[:-window] if len(series) > window else series[:1]

        recent_mean = float(np.mean(recent))
        earlier_mean = float(np.mean(earlier))
        change_pct = TrendEngine._compute_change_pct(recent_mean, earlier_mean)
        volatility = float(np.std(recent)) if len(recent) > 1 else 0.0
        direction = TrendEngine._classify_direction(change_pct)

        return {
            "direction": direction,
            "change_pct": round(change_pct, 4),
            "volatility": round(volatility, 4),
            "window_days": 7,
        }

    @staticmethod
    def compute_30day_trend(
        df: pd.DataFrame,
        metric: str,
    ) -> Dict[str, Any]:
        """Compute medium-term (30-day) trend direction and volatility.

        Args:
            df: DataFrame with time-series data.
            metric: Column name of the metric to analyze.

        Returns:
            Dict with direction, change_pct, volatility.
        """
        series = TrendEngine._extract_series(df, metric)
        if len(series) < 2:
            return {"direction": "stable", "change_pct": 0.0, "volatility": 0.0}

        window = min(30, len(series))
        recent = series[-window:]
        earlier = series[:-window] if len(series) > window else series[:1]

        recent_mean = float(np.mean(recent))
        earlier_mean = float(np.mean(earlier))
        change_pct = TrendEngine._compute_change_pct(recent_mean, earlier_mean)
        volatility = float(np.std(recent)) if len(recent) > 1 else 0.0
        direction = TrendEngine._classify_direction(change_pct)

        return {
            "direction": direction,
            "change_pct": round(change_pct, 4),
            "volatility": round(volatility, 4),
            "window_days": 30,
        }

    @staticmethod
    def moving_average(series: np.ndarray, window: int = 7) -> np.ndarray:
        """Compute simple moving average over a sliding window.

        Args:
            series: 1-D numpy array of values.
            window: Rolling window size.

        Returns:
            Numpy array of SMA values with NaN for leading positions.
        """
        if len(series) == 0 or window <= 0:
            return np.array([])
        padded = np.pad(series.astype(float), (window - 1, 0), mode="constant", constant_values=np.nan)
        cumsum = np.cumsum(np.insert(padded, 0, 0))
        sma = (cumsum[window:] - cumsum[:-window]) / window
        return sma[:len(series)]

    @staticmethod
    def detect_anomalies(
        series: np.ndarray,
        method: str = "zscore",
        threshold: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """Detect anomalous points in a time series.

        Supported methods:
            - "zscore": flags points where |z-score| > threshold
            - "iqr": flags points outside (Q1 - 1.5*IQR, Q3 + 1.5*IQR)

        Args:
            series: 1-D numpy array of values.
            method: Detection method ("zscore" or "iqr").
            threshold: Z-score threshold (default 2.0, ignored for iqr).

        Returns:
            List of anomaly dicts with index, value, z_score (or iqr_bounds).
        """
        if len(series) == 0:
            return []

        values = series.astype(float)
        anomalies: List[Dict[str, Any]] = []

        if method == "zscore":
            mean = float(np.mean(values))
            std = float(np.std(values))
            if std == 0:
                return []
            z_scores = (values - mean) / std
            anomaly_indices = np.where(np.abs(z_scores) > threshold)[0]
            for idx in anomaly_indices:
                anomalies.append({
                    "index": int(idx),
                    "value": round(float(values[idx]), 4),
                    "z_score": round(float(z_scores[idx]), 4),
                })

        elif method == "iqr":
            q1 = float(np.percentile(values, 25))
            q3 = float(np.percentile(values, 75))
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            anomaly_indices = np.where((values < lower) | (values > upper))[0]
            for idx in anomaly_indices:
                anomalies.append({
                    "index": int(idx),
                    "value": round(float(values[idx]), 4),
                    "lower_bound": round(lower, 4),
                    "upper_bound": round(upper, 4),
                })

        return anomalies

    @staticmethod
    def detect_change_points(
        series: np.ndarray,
        min_distance: int = 5,
    ) -> List[Dict[str, Any]]:
        """Detect change points using a sliding window mean shift approach.

        Compares adjacent windows; flags points where the absolute mean
        difference between left and right windows exceeds a dynamic threshold.

        Args:
            series: 1-D numpy array of values.
            min_distance: Minimum number of points between change points.

        Returns:
            List of change point dicts with index, left_mean, right_mean, delta.
        """
        if len(series) < min_distance * 2:
            return []

        values = series.astype(float)
        window_size = max(3, min_distance // 2)
        change_points: List[Dict[str, Any]] = []
        last_change = -min_distance

        for i in range(window_size, len(values) - window_size):
            if i - last_change < min_distance:
                continue
            left = values[i - window_size : i]
            right = values[i : i + window_size]
            left_mean = float(np.mean(left))
            right_mean = float(np.mean(right))
            delta = abs(right_mean - left_mean)
            combined_std = float(np.std(np.concatenate([left, right])))

            if combined_std == 0:
                continue

            threshold = 1.5 * combined_std / np.sqrt(window_size)
            if delta > threshold:
                change_points.append({
                    "index": i,
                    "left_mean": round(left_mean, 4),
                    "right_mean": round(right_mean, 4),
                    "delta": round(delta, 4),
                })
                last_change = i

        return change_points

    @staticmethod
    def compute_seasonality(
        series: np.ndarray,
        period: int = 7,
    ) -> np.ndarray:
        """Compute the seasonal component using a simple period-averaging approach.

        Decomposes series into average values for each position within the period.

        Args:
            series: 1-D numpy array of values.
            period: Number of data points per cycle (default 7 for weekly).

        Returns:
            Numpy array of seasonal factors (same length as series).
        """
        if len(series) == 0 or period <= 0:
            return np.array([])

        values = series.astype(float)
        n_cycles = len(values) // period

        if n_cycles < 1:
            seasonal_pattern = np.full(period, float(np.mean(values)))
        else:
            trimmed = values[: n_cycles * period]
            reshaped = trimmed.reshape(n_cycles, period)
            seasonal_pattern = np.mean(reshaped, axis=0)

        seasonal = np.tile(seasonal_pattern, (len(values) + period - 1) // period)[:len(values)]
        return seasonal

    @staticmethod
    def compare_periods(
        df: pd.DataFrame,
        metric: str,
        period1: Tuple[str, str],
        period2: Tuple[str, str],
    ) -> Dict[str, Any]:
        """Compare a metric between two time periods.

        Args:
            df: DataFrame with a 'timestamp' or 'date' datetime column.
            metric: Column name of the metric to compare.
            period1: (start, end) date strings for first period.
            period2: (start, end) date strings for second period.

        Returns:
            Dict with p1_mean, p2_mean, delta, change_pct, significance,
            p_value (if scipy available).
        """
        time_col = "timestamp" if "timestamp" in df.columns else "date"
        df = df.copy()
        df[time_col] = pd.to_datetime(df[time_col])

        mask1 = (df[time_col] >= pd.to_datetime(period1[0])) & (df[time_col] <= pd.to_datetime(period1[1]))
        mask2 = (df[time_col] >= pd.to_datetime(period2[0])) & (df[time_col] <= pd.to_datetime(period2[1]))

        p1_values = df.loc[mask1, metric].values.astype(float)
        p2_values = df.loc[mask2, metric].values.astype(float)

        p1_mean = float(np.mean(p1_values)) if len(p1_values) > 0 else 0.0
        p2_mean = float(np.mean(p2_values)) if len(p2_values) > 0 else 0.0

        change_pct = TrendEngine._compute_change_pct(p2_mean, p1_mean)
        delta = round(p2_mean - p1_mean, 4)

        significance = "stable"
        p_value: Optional[float] = None

        if len(p1_values) > 1 and len(p2_values) > 1 and HAS_SCIPY:
            try:
                _, p_value = scipy_stats.ttest_ind(p1_values, p2_values, equal_var=False)
                p_value = round(float(p_value), 6)
                if p_value is not None:
                    if p_value < 0.01:
                        significance = "highly_significant"
                    elif p_value < 0.05:
                        significance = "significant"
                    elif p_value < 0.1:
                        significance = "weakly_significant"
            except Exception:
                pass
        elif abs(change_pct) > 10:
            significance = "notable"
        elif abs(change_pct) > 5:
            significance = "minor"

        return {
            "p1_mean": round(p1_mean, 4),
            "p2_mean": round(p2_mean, 4),
            "delta": delta,
            "change_pct": round(change_pct, 4),
            "p1_size": len(p1_values),
            "p2_size": len(p2_values),
            "significance": significance,
            "p_value": p_value,
        }

    @staticmethod
    def forecast_linear(
        series: np.ndarray,
        periods: int = 7,
    ) -> np.ndarray:
        """Forecast future values using linear regression.

        Uses sklearn LinearRegression if available, falls back to
        numpy polyfit.

        Args:
            series: 1-D numpy array of historical values.
            periods: Number of future periods to forecast.

        Returns:
            Numpy array of forecasted values (length = periods).
        """
        if len(series) == 0 or periods <= 0:
            return np.array([])

        x = np.arange(len(series)).reshape(-1, 1)
        y = series.astype(float)

        if HAS_SKLEARN:
            model = LinearRegression()
            model.fit(x, y)
            x_future = np.arange(len(series), len(series) + periods).reshape(-1, 1)
            forecast = model.predict(x_future)
        else:
            coeffs = np.polyfit(x.flatten(), y, 1)
            poly = np.poly1d(coeffs)
            x_future = np.arange(len(series), len(series) + periods)
            forecast = poly(x_future)

        return np.round(forecast, 4)

    @staticmethod
    def compute_correlation(
        series1: np.ndarray,
        series2: np.ndarray,
    ) -> float:
        """Compute Pearson correlation between two series.

        Uses scipy.stats.pearsonr if available, otherwise numpy.corrcoef.

        Args:
            series1: First series.
            series2: Second series.

        Returns:
            Pearson correlation coefficient. Returns 0.0 on error or
            if arrays differ in length.
        """
        if len(series1) != len(series2) or len(series1) < 2:
            return 0.0

        s1 = series1.astype(float)
        s2 = series2.astype(float)

        try:
            if HAS_SCIPY:
                corr, _ = scipy_stats.pearsonr(s1, s2)
                return round(float(corr), 6)
            corr_matrix = np.corrcoef(s1, s2)
            return round(float(corr_matrix[0, 1]), 6)
        except Exception:
            return 0.0

    @staticmethod
    def _extract_series(df: pd.DataFrame, metric: str) -> np.ndarray:
        """Extract a sorted 1-D numpy array from a DataFrame."""
        if df.empty or metric not in df.columns:
            return np.array([])
        time_col = "timestamp" if "timestamp" in df.columns else "date"
        if time_col in df.columns:
            sorted_df = df.sort_values(time_col)
        else:
            sorted_df = df
        return sorted_df[metric].values.astype(float)

    @staticmethod
    def _compute_change_pct(new_val: float, old_val: float) -> float:
        """Compute percentage change, handling division by zero."""
        if old_val == 0:
            return 0.0
        return ((new_val - old_val) / abs(old_val)) * 100

    @staticmethod
    def _classify_direction(change_pct: float) -> str:
        """Classify direction from percentage change."""
        if change_pct > 5:
            return "up"
        if change_pct < -5:
            return "down"
        return "stable"
