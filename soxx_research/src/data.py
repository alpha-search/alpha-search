"""
Stage 1 — DATA
==============
Pull SOXX / SMH / NVDA intraday bars, clean them, cache to disk.

Primary source: yfinance (Yahoo). 5-minute bars are capped at 60 calendar days,
1-minute bars at 7 days. We pull 5m as the primary series and 1m (7d) as a
robustness check.

IMPORTANT — offline fallback
----------------------------
If Yahoo is unreachable (e.g. locked-down sandbox egress policy), this module
falls back to a *clearly labeled* synthetic generator so the rest of the
pipeline can be exercised end-to-end. Every cached file and every DataFrame is
tagged with a `source` attribute in `data/_provenance.json`. Synthetic data is
NEVER evidence of real alpha — it exists only to prove the code runs. Run this
on a machine with Yahoo access (your phone) to get real bars.
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

TICKERS = ["SOXX", "SMH", "NVDA"]
RTH_START = "09:30"
RTH_END = "16:00"          # inclusive of the 15:55 bar; 16:00 close bar dropped
BARS_PER_DAY_5M = 78       # 09:30..15:55 inclusive
TZ = "America/New_York"
PROV_PATH = os.path.join(DATA_DIR, "_provenance.json")


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #
def _write_provenance(d: dict) -> None:
    prov = {}
    if os.path.exists(PROV_PATH):
        try:
            prov = json.load(open(PROV_PATH))
        except Exception:
            prov = {}
    prov.update(d)
    json.dump(prov, open(PROV_PATH, "w"), indent=2, default=str)


def get_provenance() -> dict:
    if os.path.exists(PROV_PATH):
        return json.load(open(PROV_PATH))
    return {}


# --------------------------------------------------------------------------- #
# yfinance download
# --------------------------------------------------------------------------- #
def _yf_download(ticker: str, interval: str, days: int) -> pd.DataFrame:
    """Return raw OHLCV from Yahoo, or empty DataFrame on failure."""
    import yfinance as yf

    period = f"{days}d"
    df = yf.download(
        ticker, period=period, interval=interval,
        progress=False, auto_adjust=False, prepost=True, threads=False,
    )
    if df is None or len(df) == 0:
        return pd.DataFrame()
    # yfinance may return a MultiIndex column frame for a single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)
    keep = ["Open", "High", "Low", "Close", "Volume"]
    df = df[[c for c in keep if c in df.columns]].copy()
    # localize / convert to NY
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(TZ)
    df.index.name = "datetime"
    return df


# --------------------------------------------------------------------------- #
# Synthetic fallback generator
# --------------------------------------------------------------------------- #
def _synth_calendar(days: int, interval_min: int) -> pd.DatetimeIndex:
    """Business-day RTH timestamps for the last `days` calendar days."""
    end = pd.Timestamp("2026-08-06 16:00", tz=TZ)          # deterministic anchor
    start = end - pd.Timedelta(days=days)
    bdays = pd.bdate_range(start.date(), end.date(), tz=TZ)
    stamps = []
    n_per = int((6.5 * 60) / interval_min)                  # 78 for 5m
    for d in bdays:
        base = pd.Timestamp(f"{d.date()} 09:30", tz=TZ)
        stamps.extend(base + pd.Timedelta(minutes=interval_min) * k for k in range(n_per))
    return pd.DatetimeIndex(stamps, name="datetime")


def _synth_prices(idx: pd.DatetimeIndex, seed: int, spot: float,
                  ann_vol: float, drift: float,
                  common: np.ndarray | None = None,
                  beta: float = 0.0) -> pd.DataFrame:
    """
    Generate realistic-looking intraday OHLCV, built session-by-session:
      * a genuine overnight GAP applied to each session's OPEN price,
      * a mild U-shaped intraday vol smile,
      * an idiosyncratic + common-factor return decomposition (for correlation).
    This is DELIBERATELY close to a random walk: any 'signal' found on it is,
    by construction, luck. That is the point of the honesty test.
    """
    rng = np.random.default_rng(seed)
    n = len(idx)
    per_bar = ann_vol / np.sqrt(252 * BARS_PER_DAY_5M)
    mu = drift / (252 * BARS_PER_DAY_5M)
    overnight_sd = (ann_vol / np.sqrt(252)) * 0.7

    minute_of_day = (idx.hour * 60 + idx.minute - 570).to_numpy()
    frac = minute_of_day / 385.0
    smile = 0.7 + 0.9 * (2 * frac - 1) ** 2

    if common is None:
        common = np.zeros(n)
    idio = rng.standard_normal(n)
    shock = idio * np.sqrt(max(1e-9, 1 - beta ** 2)) + beta * common
    ret = mu + per_bar * smile * shock              # intraday bar returns (no overnight)

    day = idx.normalize().to_numpy()
    new_session = np.r_[True, day[1:] != day[:-1]]
    session_starts = np.where(new_session)[0]

    openp = np.empty(n)
    close = np.empty(n)
    prev_close = spot
    for si, start in enumerate(session_starts):
        end = session_starts[si + 1] if si + 1 < len(session_starts) else n
        gap = rng.standard_normal() * overnight_sd
        o0 = prev_close * np.exp(gap)               # overnight gap lives in the OPEN
        c = o0
        for i in range(start, end):
            o = c if i > start else o0
            c = o * np.exp(ret[i])
            openp[i] = o
            close[i] = c
        prev_close = c

    wig = np.abs(rng.standard_normal(n)) * per_bar * 0.8 * close
    high = np.maximum(openp, close) + wig
    low = np.minimum(openp, close) - wig
    vol = (rng.lognormal(mean=11.5, sigma=0.5, size=n) * smile).astype(np.int64)

    df = pd.DataFrame(
        {"Open": openp, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )
    return df, ret


def _generate_synthetic(interval: str, days: int) -> dict[str, pd.DataFrame]:
    interval_min = int(interval.replace("m", ""))
    idx = _synth_calendar(days, interval_min)
    rng = np.random.default_rng(20260806)
    # a shared 'semiconductor sector' factor drives cross-asset correlation
    common = rng.standard_normal(len(idx))
    out = {}
    specs = {
        "SOXX": dict(seed=1, spot=235.0, ann_vol=0.28, drift=0.08, beta=0.92),
        "SMH":  dict(seed=2, spot=250.0, ann_vol=0.30, drift=0.09, beta=0.94),
        "NVDA": dict(seed=3, spot=118.0, ann_vol=0.48, drift=0.15, beta=0.85),
    }
    for t, s in specs.items():
        df, _ = _synth_prices(idx, common=common, **s)
        out[t] = df
    return out


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def clean_intraday(df: pd.DataFrame, interval: str, log: list) -> pd.DataFrame:
    """Drop pre/post market, dedupe, verify bar counts per day, log anomalies."""
    if df.empty:
        return df
    df = df[~df.index.duplicated(keep="first")].sort_index()

    # Restrict to regular trading hours 09:30–15:55 (drop the 16:00 stub + pre/post)
    t = df.index.tz_convert(TZ)
    mins = t.hour * 60 + t.minute
    rth = (mins >= 570) & (mins <= 955)            # 09:30 .. 15:55
    dropped = int((~rth).sum())
    df = df[rth]
    if dropped:
        log.append(f"  dropped {dropped} pre/post-market bars")

    # drop rows with any NaN / non-positive prices
    bad = df[["Open", "High", "Low", "Close"]].le(0).any(axis=1) | df.isna().any(axis=1)
    if bad.any():
        log.append(f"  dropped {int(bad.sum())} bad/zero/NaN rows")
        df = df[~bad]

    # per-day bar-count audit
    expected = BARS_PER_DAY_5M if interval == "5m" else int(6.5 * 60 // int(interval.replace("m", "")))
    counts = df.groupby(df.index.normalize()).size()
    short_days = counts[counts < expected]
    if len(short_days):
        log.append(f"  {len(short_days)}/{len(counts)} days short of {expected} bars "
                   f"(min={int(counts.min())}); half-days/gaps expected")
    # flag internal gaps > 1 bar
    step = pd.Timedelta(minutes=int(interval.replace("m", "")))
    gaps = df.index.to_series().diff()
    intraday = gaps[(gaps > step) & (gaps < pd.Timedelta(hours=2))]
    if len(intraday):
        log.append(f"  {len(intraday)} intraday gaps > 1 bar (missing prints)")
    return df


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def load(interval: str = "5m", days: int = 60, force: bool = False) -> dict[str, pd.DataFrame]:
    """
    Return {ticker: cleaned OHLCV DataFrame}. Cached to data/<ticker>_<interval>.parquet.
    Tries Yahoo; falls back to synthetic (clearly labeled in provenance) if offline.
    """
    tag = f"{interval}_{days}d"
    # cache keyed by (interval, days) so a short live-pull never clobbers the
    # 60-day research cache
    cpath = lambda t: os.path.join(DATA_DIR, f"{t}_{tag}.parquet")
    cache_ok = all(os.path.exists(cpath(t)) for t in TICKERS)
    if cache_ok and not force:
        out = {t: pd.read_parquet(cpath(t)) for t in TICKERS}
        prov = get_provenance().get(tag, "cached")
        print(f"[stage1] loaded {tag} from cache ({prov}): "
              + ", ".join(f"{t}={len(v)}" for t, v in out.items()))
        return out

    log = [f"[stage1] fetch {interval} last {days}d"]
    source = "yfinance"
    raw = {}
    for t in TICKERS:
        try:
            df = _yf_download(t, interval, days)
        except Exception as e:
            df = pd.DataFrame()
            log.append(f"  {t}: yfinance error: {type(e).__name__}")
        raw[t] = df

    if any(v.empty for v in raw.values()):
        source = "SYNTHETIC"
        log.append("  !! Yahoo unreachable -> SYNTHETIC fallback (NOT real data)")
        raw = _generate_synthetic(interval, days)

    out = {}
    for t in TICKERS:
        log.append(f"  {t}: {len(raw[t])} raw bars")
        cleaned = clean_intraday(raw[t], interval, log)
        cleaned.to_parquet(cpath(t))
        cleaned.to_csv(os.path.join(DATA_DIR, f"{t}_{tag}.csv"))
        out[t] = cleaned

    prov_update = {tag: source, interval: source,
                   f"{tag}_fetched_utc": datetime.utcnow().isoformat()}
    _write_provenance(prov_update)
    print("\n".join(log))
    print(f"[stage1] SOURCE = {source}  ({tag})")
    return out


if __name__ == "__main__":
    d5 = load("5m", 60, force="--force" in sys.argv)
    d1 = load("1m", 7, force="--force" in sys.argv)
    prov = get_provenance()
    print(f"[stage1] provenance: {prov}")
    for t, df in d5.items():
        ndays = df.index.normalize().nunique()
        print(f"[stage1] {t} 5m: {len(df)} bars, {ndays} sessions, "
              f"{df.index.min()} -> {df.index.max()}")
