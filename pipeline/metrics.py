"""Turns raw DataLab ratios into a comparable, honest demand index.

DataLab ratios are relative inside a single request (max = 100). Every request
for a segment includes the same anchor keyword, so dividing by the anchor's mean
inside that request puts all keywords on one scale: anchor average = 100.
"""
import datetime as dt
import math


def date_range(start, end):
    d0 = dt.date.fromisoformat(start)
    d1 = dt.date.fromisoformat(end)
    return [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def mean(values):
    return sum(values) / len(values) if values else 0.0


def normalize_batch(batch, anchor_kw, dates):
    """batch: {kw: {date: ratio}} from one request. Returns {kw: [index per date]}."""
    anchor_series = [batch.get(anchor_kw, {}).get(d, 0.0) for d in dates]
    scale = mean(anchor_series)
    if scale <= 0:
        raise ValueError("Anchor keyword returned no data; cannot normalize batch")
    out = {}
    for kw, series in batch.items():
        out[kw] = [series.get(d, 0.0) / scale * 100.0 for d in dates]
    return out


def keyword_metrics(series, recent_days, baseline_days, min_level):
    """series: index values ordered oldest -> newest."""
    if len(series) < recent_days + baseline_days:
        raise ValueError("Series shorter than recent + baseline window")
    for v in series:
        if not math.isfinite(v) or v < 0:
            raise ValueError("Invalid value in series")
    recent = series[-recent_days:]
    baseline = series[-(recent_days + baseline_days):-recent_days]
    level = mean(recent)
    base = mean(baseline)
    prev_week = mean(series[-2 * recent_days:-recent_days])
    early_base = mean(series[-(recent_days + baseline_days):-2 * recent_days])
    momentum = None
    if base >= min_level and level >= min_level:
        momentum = level / base - 1.0
    return {
        "level": round(level, 2),
        "baseline": round(base, 2),
        "prev_week": round(prev_week, 2),
        "early_baseline": round(early_base, 2),
        "momentum": None if momentum is None else round(momentum, 4),
        "series": [round(v, 2) for v in series],
    }
