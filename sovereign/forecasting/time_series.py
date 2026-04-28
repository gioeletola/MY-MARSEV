"""Time-series utilities — moving averages, trend fitting, seasonality, forecasting."""
from __future__ import annotations

from collections import deque
from typing import Literal


# ── Moving Average ────────────────────────────────────────────────────────────

class MovingAverage:
    """Simple (unweighted) moving average over a fixed window."""

    def __init__(self, window: int) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        self._window = window
        self._buf: deque[float] = deque(maxlen=window)

    def update(self, value: float) -> None:
        self._buf.append(float(value))

    @property
    def current(self) -> float:
        if not self._buf:
            return float("nan")
        return sum(self._buf) / len(self._buf)

    @property
    def is_ready(self) -> bool:
        """True once the buffer has been filled to full window size."""
        return len(self._buf) == self._window


# ── Exponential Smoothing ─────────────────────────────────────────────────────

class ExponentialSmoothing:
    """Exponential Moving Average (EMA).

    ``alpha`` controls smoothing: higher = faster response to new values.
    """

    def __init__(self, alpha: float = 0.3) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self._alpha = alpha
        self._ema: float | None = None

    def update(self, value: float) -> float:
        v = float(value)
        if self._ema is None:
            self._ema = v
        else:
            self._ema = self._alpha * v + (1.0 - self._alpha) * self._ema
        return self._ema

    @property
    def current(self) -> float:
        return self._ema if self._ema is not None else float("nan")

    def reset(self) -> None:
        self._ema = None


# ── Linear Trend ──────────────────────────────────────────────────────────────

def LinearTrend(values: list[float]) -> tuple[float, float, float]:
    """Ordinary least-squares linear trend fit.

    Returns (slope, intercept, r²).
    A positive slope indicates an upward trend.
    """
    n = len(values)
    if n < 2:
        raise ValueError("Need at least 2 values for LinearTrend")

    x_vals = list(range(n))
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
    ss_xx = sum((x - x_mean) ** 2 for x in x_vals)

    if ss_xx == 0:
        return 0.0, y_mean, float("nan")

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    # R²
    y_predicted = [slope * x + intercept for x in x_vals]
    ss_res = sum((y - yp) ** 2 for y, yp in zip(values, y_predicted))
    ss_tot = sum((y - y_mean) ** 2 for y in values)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return round(slope, 6), round(intercept, 6), round(r2, 6)


# ── Seasonality Detection ─────────────────────────────────────────────────────

def detect_seasonality(values: list[float], period: int) -> bool:
    """Detect whether *values* exhibits periodicity of length *period*.

    Uses autocorrelation at lag *period*. Returns True if correlation > 0.5.
    """
    n = len(values)
    if n < period * 2 or period < 1:
        return False

    mean = sum(values) / n
    demeaned = [v - mean for v in values]

    # Autocorrelation at lag = period
    numerator = sum(demeaned[i] * demeaned[i + period] for i in range(n - period))
    denominator = sum(d ** 2 for d in demeaned)

    if denominator == 0:
        return False

    acf = numerator / denominator
    return acf > 0.5


# ── Forecasting ───────────────────────────────────────────────────────────────

def forecast_next_n(
    values: list[float],
    n: int,
    method: Literal["ema", "sma", "linear"] = "ema",
    alpha: float = 0.3,
    window: int = 5,
) -> list[float]:
    """Forecast the next *n* values after *values* using the chosen method.

    Methods:
      ``ema``    — Exponential Moving Average projection (repeats last EMA).
      ``sma``    — Simple Moving Average projection (repeats last SMA).
      ``linear`` — Extrapolates the least-squares linear trend.
    """
    if not values:
        return [float("nan")] * n
    if n < 1:
        return []

    if method == "ema":
        smoother = ExponentialSmoothing(alpha=alpha)
        for v in values:
            smoother.update(v)
        last = smoother.current
        return [round(last, 6)] * n

    elif method == "sma":
        ma = MovingAverage(window=min(window, len(values)))
        for v in values:
            ma.update(v)
        last = ma.current
        return [round(last, 6)] * n

    elif method == "linear":
        slope, intercept, _ = LinearTrend(values)
        base_idx = len(values)
        return [round(slope * (base_idx + i) + intercept, 6) for i in range(n)]

    else:
        raise ValueError(f"Unknown forecast method: {method!r}. Use 'ema', 'sma', or 'linear'.")
