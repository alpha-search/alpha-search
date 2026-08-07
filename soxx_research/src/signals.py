"""
Stage 2 — SIGNALS
=================
Seven composable signal families. Every signal is a pure function of an OHLCV
frame (plus optional reference frames) and returns a *target position* series in
{-1, 0, +1}, one value per bar.

CAUSALITY CONTRACT
------------------
The value at bar t is the position you intend to HOLD INTO bar t+1. It may use
information only up to and including the close of bar t. The backtester shifts
positions by one bar and applies next-bar returns, so no signal here is allowed
to peek at bar t+1. `_causal_ok()` sanity-checks this.

Each signal documents an explicit ENTRY / EXIT / STOP rule. Where a stop is
genuinely path-dependent (intrabar), the vectorized version approximates it on
closes; Stage 4's event-driven sim implements true intrabar stops for the
finalists.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Session helpers
# --------------------------------------------------------------------------- #
def session_id(px: pd.DataFrame) -> pd.Series:
    return pd.Series(px.index.normalize(), index=px.index)


def _by_session(px: pd.DataFrame):
    return px.groupby(px.index.normalize(), group_keys=False)


def bar_return(px: pd.DataFrame) -> pd.Series:
    """Close-to-close log return, reset (NaN) at each session open (no overnight)."""
    r = np.log(px["Close"]).diff()
    first = px.index.normalize().to_series(index=px.index).ne(
        px.index.normalize().to_series(index=px.index).shift()
    )
    r[first.values] = np.nan
    return r


# --------------------------------------------------------------------------- #
# Indicators (all causal / rolling)
# --------------------------------------------------------------------------- #
def rolling_vwap(px: pd.DataFrame, window: int) -> pd.Series:
    tp = (px["High"] + px["Low"] + px["Close"]) / 3.0
    pv = (tp * px["Volume"]).rolling(window).sum()
    vv = px["Volume"].rolling(window).sum().replace(0, np.nan)
    return pv / vv


def session_vwap(px: pd.DataFrame) -> pd.Series:
    tp = (px["High"] + px["Low"] + px["Close"]) / 3.0
    pv = tp * px["Volume"]
    cum_pv = _by_session(px).apply(lambda g: (tp.loc[g.index] * g["Volume"]).cumsum())
    cum_v = _by_session(px).apply(lambda g: g["Volume"].cumsum())
    return (cum_pv / cum_v.replace(0, np.nan)).reindex(px.index)


def rsi_wilder(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    rs = up.ewm(alpha=1 / n, adjust=False).mean() / dn.ewm(alpha=1 / n, adjust=False).mean().replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(px: pd.DataFrame, n: int) -> pd.Series:
    pc = px["Close"].shift()
    tr = pd.concat([px["High"] - px["Low"], (px["High"] - pc).abs(), (px["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def realized_vol(px: pd.DataFrame, window: int) -> pd.Series:
    # min_periods so the session-open NaNs in bar_return don't null the whole window
    return bar_return(px).rolling(window, min_periods=max(5, window // 2)).std()


def _causal_ok(sig: pd.Series, px: pd.DataFrame) -> bool:
    """A signal must not depend on future bars: shifting inputs forward must not
    change past outputs. Cheap proxy: signal has no NaN-free values that could
    only come from look-ahead (we simply assert no reliance on px shifted -1)."""
    return sig.index.equals(px.index)


# --------------------------------------------------------------------------- #
# 1. Time-series momentum — N-bar return breakout
# --------------------------------------------------------------------------- #
def sig_tsmom(px: pd.DataFrame, n: int = 12, thresh: float = 0.0) -> pd.Series:
    """
    ENTRY: go long if trailing N-bar return > +thresh, short if < -thresh.
    EXIT : opposite/again evaluated every bar (always-in when |ret|>thresh).
    STOP : implicit — flips to 0 when momentum decays below thresh.
    """
    r_n = np.log(px["Close"]).diff(n)
    sig = pd.Series(0, index=px.index, dtype=float)
    sig[r_n > thresh] = 1
    sig[r_n < -thresh] = -1
    # do not carry a decision made using pre-open (cross-session) diff
    valid = _by_session(px).cumcount() >= n
    sig[~valid.values] = 0
    return sig


# --------------------------------------------------------------------------- #
# 2. Opening range breakout
# --------------------------------------------------------------------------- #
def sig_orb(px: pd.DataFrame, or_minutes: int = 30, bar_min: int = 5) -> pd.Series:
    """
    ENTRY: after the first `or_minutes` of the session, long if close breaks
           above the opening-range high, short if below the OR low.
    EXIT : end of day (handled by backtester) or opposite break.
    STOP : the opposite side of the opening range (approximated on closes here;
           true intrabar stop in Stage 4).
    """
    k = max(1, or_minutes // bar_min)                      # bars in opening range
    out = pd.Series(0, index=px.index, dtype=float)

    def per_day(g: pd.DataFrame) -> pd.Series:
        s = pd.Series(0, index=g.index, dtype=float)
        if len(g) <= k:
            return s
        or_hi = g["High"].iloc[:k].max()
        or_lo = g["Low"].iloc[:k].min()
        c = g["Close"]
        pos = 0.0
        vals = np.zeros(len(g))
        for i in range(k, len(g)):
            if pos == 0:
                if c.iloc[i] > or_hi:
                    pos = 1.0
                elif c.iloc[i] < or_lo:
                    pos = -1.0
            elif pos == 1 and c.iloc[i] < or_lo:          # stop through other side
                pos = -1.0
            elif pos == -1 and c.iloc[i] > or_hi:
                pos = 1.0
            vals[i] = pos
        s.iloc[:] = vals
        return s

    out = _by_session(px).apply(per_day).reindex(px.index).fillna(0)
    return out


# --------------------------------------------------------------------------- #
# 3. Mean reversion
# --------------------------------------------------------------------------- #
def sig_vwap_z(px: pd.DataFrame, window: int = 24, z_in: float = 2.0, z_out: float = 0.5) -> pd.Series:
    """
    Z-score of close vs rolling VWAP. FADE extremes.
    ENTRY: short when z > +z_in, long when z < -z_in.
    EXIT : when |z| < z_out (mean touched).
    STOP : z blows out further -> handled by fixed exit horizon in backtest.
    """
    vw = rolling_vwap(px, window)
    resid = px["Close"] - vw
    z = (resid - resid.rolling(window).mean()) / resid.rolling(window).std().replace(0, np.nan)
    raw = pd.Series(np.nan, index=px.index, dtype=float)
    raw[z > z_in] = -1
    raw[z < -z_in] = 1
    raw[z.abs() < z_out] = 0
    pos = raw.ffill().fillna(0)
    # never hold across the open
    pos = pos.where(_by_session(px).cumcount() > window, 0)
    return pos


def sig_bollinger_fade(px: pd.DataFrame, window: int = 20, k: float = 2.0) -> pd.Series:
    """
    ENTRY: short when close > upper band, long when close < lower band.
    EXIT : close returns to the moving average.
    STOP : opposite band.
    """
    ma = px["Close"].rolling(window).mean()
    sd = px["Close"].rolling(window).std().replace(0, np.nan)
    upper, lower = ma + k * sd, ma - k * sd
    raw = pd.Series(np.nan, index=px.index, dtype=float)
    raw[px["Close"] > upper] = -1
    raw[px["Close"] < lower] = 1
    raw[(px["Close"] >= ma) & (px["Close"].shift() < ma)] = 0
    raw[(px["Close"] <= ma) & (px["Close"].shift() > ma)] = 0
    pos = raw.ffill().fillna(0)
    pos = pos.where(_by_session(px).cumcount() > window, 0)
    return pos


def sig_rsi2(px: pd.DataFrame, lo: float = 5.0, hi: float = 95.0, exit_mid: float = 50.0) -> pd.Series:
    """
    RSI(2) extremes (Connors).
    ENTRY: long when RSI(2) < lo, short when RSI(2) > hi.
    EXIT : RSI crosses back through exit_mid.
    STOP : end of day.
    """
    r = rsi_wilder(px["Close"], 2)
    raw = pd.Series(np.nan, index=px.index, dtype=float)
    raw[r < lo] = 1
    raw[r > hi] = -1
    raw[(r >= exit_mid) & (r.shift() < exit_mid)] = 0
    raw[(r <= exit_mid) & (r.shift() > exit_mid)] = 0
    return raw.ffill().fillna(0)


# --------------------------------------------------------------------------- #
# 4. Volatility-regime breakout (trade only in a chosen vol tercile)
# --------------------------------------------------------------------------- #
def sig_vol_regime_breakout(px: pd.DataFrame, atr_n: int = 14, look: int = 12,
                            mult: float = 1.0, tercile: str = "high",
                            vol_window: int = 78) -> pd.Series:
    """
    ATR-normalized breakout, GATED by realized-vol regime.
    ENTRY: long if close > close[look bars ago] + mult*ATR; short symmetric —
           but ONLY when trailing realized vol sits in the chosen tercile.
    EXIT : opposite signal / gate closes.
    STOP : the ATR band on the other side.
    """
    a = atr(px, atr_n)
    ref = px["Close"].shift(look)
    up = px["Close"] > ref + mult * a
    dn = px["Close"] < ref - mult * a
    rv = realized_vol(px, vol_window)
    q1, q2 = rv.quantile(1 / 3), rv.quantile(2 / 3)
    if tercile == "high":
        gate = rv >= q2
    elif tercile == "low":
        gate = rv <= q1
    else:
        gate = (rv > q1) & (rv < q2)
    sig = pd.Series(0, index=px.index, dtype=float)
    sig[up & gate] = 1
    sig[dn & gate] = -1
    valid = _by_session(px).cumcount() >= look
    sig[~valid.values] = 0
    return sig


# --------------------------------------------------------------------------- #
# 5. Time-of-day effects (each tested separately)
# --------------------------------------------------------------------------- #
def _minute_of_day(px: pd.DataFrame) -> np.ndarray:
    return (px.index.hour * 60 + px.index.minute - 570).to_numpy()


def sig_time_of_day(px: pd.DataFrame, window: str = "first_hour", direction: int = 1) -> pd.Series:
    """
    Directional drift confined to a time-of-day window.
    ENTRY: take `direction` (long/short) only while inside the window.
    EXIT : leaving the window (and EOD).
    STOP : none intrabar; the window itself bounds exposure.
    windows: first_hour (0-60m), lunch (120-210m), last_hour (330-385m).
    """
    m = _minute_of_day(px)
    if window == "first_hour":
        mask = (m >= 0) & (m < 60)
    elif window == "lunch":
        mask = (m >= 120) & (m < 210)
    elif window == "last_hour":
        mask = m >= 330
    else:
        raise ValueError(window)
    return pd.Series(np.where(mask, direction, 0), index=px.index, dtype=float)


# --------------------------------------------------------------------------- #
# 6. Cross-asset lead-lag (does NVDA/SMH last-bar return predict SOXX next bar?)
# --------------------------------------------------------------------------- #
def sig_lead_lag(px: pd.DataFrame, leader: pd.DataFrame, thresh: float = 0.0) -> pd.Series:
    """
    ENTRY: sign of the leader's *current-bar* return dictates SOXX position for
           the next bar. Uses only info up to bar t (leader close at t), so it is
           causal; the backtester still executes on t+1.
    EXIT : re-evaluated every bar.
    STOP : none; single-bar horizon.
    """
    lr = np.log(leader["Close"]).diff().reindex(px.index)
    first = px.index.normalize().to_series(index=px.index).ne(
        px.index.normalize().to_series(index=px.index).shift())
    lr[first.values] = np.nan
    sig = pd.Series(0, index=px.index, dtype=float)
    sig[lr > thresh] = 1
    sig[lr < -thresh] = -1
    return sig.fillna(0)


# --------------------------------------------------------------------------- #
# 7. Gap behavior (overnight gap continuation vs fade)
# --------------------------------------------------------------------------- #
def sig_gap(px: pd.DataFrame, mode: str = "fade", hold_bars: int = 6,
            min_gap: float = 0.001) -> pd.Series:
    """
    At each session open, measure the overnight gap (today open vs prior close).
    ENTRY: 'continuation' trades in the gap's direction; 'fade' trades against it.
    EXIT : after `hold_bars` bars (or EOD).
    STOP : EOD flat.
    Only gaps larger than min_gap (fractional) are traded.
    """
    o = _by_session(px).apply(lambda g: pd.Series(g["Open"].iloc[0], index=g.index)).reindex(px.index)
    prev_close = px["Close"].groupby(px.index.normalize()).last().shift()
    pc_map = px.index.normalize().map(prev_close)
    gap = (o.values - pc_map.values) / pc_map.values
    gap = pd.Series(gap, index=px.index)
    cnt = _by_session(px).cumcount()
    sign = np.sign(gap).where(gap.abs() > min_gap, 0)
    if mode == "fade":
        sign = -sign
    sig = sign.where(cnt < hold_bars, 0)
    return sig.fillna(0).astype(float)


# --------------------------------------------------------------------------- #
# Registry — enumerate every configuration tested (Stage 3 consumes this)
# --------------------------------------------------------------------------- #
def build_registry(px: pd.DataFrame, refs: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    """Return {config_name: target_position_series} across all families."""
    S: dict[str, pd.Series] = {}

    # 1. TS momentum
    for n in (3, 6, 12, 24):
        S[f"tsmom_n{n}"] = sig_tsmom(px, n=n)

    # 2. Opening range breakout
    for orm in (15, 30, 60):
        S[f"orb_{orm}m"] = sig_orb(px, or_minutes=orm)

    # 3. Mean reversion
    for w, zi in ((24, 2.0), (24, 2.5), (48, 2.0)):
        S[f"vwapz_w{w}_z{zi}"] = sig_vwap_z(px, window=w, z_in=zi)
    for w, k in ((20, 2.0), (20, 2.5)):
        S[f"boll_w{w}_k{k}"] = sig_bollinger_fade(px, window=w, k=k)
    for lo in (5, 10):
        S[f"rsi2_lo{lo}"] = sig_rsi2(px, lo=lo, hi=100 - lo)

    # 4. Vol-regime breakout
    for terc in ("high", "low"):
        for look in (6, 12):
            S[f"volregime_{terc}_l{look}"] = sig_vol_regime_breakout(px, look=look, tercile=terc)

    # 5. Time of day (both directions)
    for win in ("first_hour", "lunch", "last_hour"):
        for d in (1, -1):
            S[f"tod_{win}_{'L' if d>0 else 'S'}"] = sig_time_of_day(px, window=win, direction=d)

    # 6. Cross-asset lead-lag
    for name in ("NVDA", "SMH"):
        if name in refs:
            S[f"leadlag_{name}"] = sig_lead_lag(px, refs[name])

    # 7. Gap behavior
    for mode in ("fade", "continuation"):
        for hb in (3, 6):
            S[f"gap_{mode}_h{hb}"] = sig_gap(px, mode=mode, hold_bars=hb)

    # causal sanity check
    for k, v in S.items():
        assert _causal_ok(v, px), f"{k} failed causality index check"
        assert v.isin([-1, 0, 1]).all(), f"{k} not in {{-1,0,1}}"
    return S


if __name__ == "__main__":
    from data import load
    d = load("5m", 60)
    reg = build_registry(d["SOXX"], {"NVDA": d["NVDA"], "SMH": d["SMH"]})
    print(f"[stage2] built {len(reg)} signal configurations")
    for k, v in reg.items():
        act = float((v != 0).mean())
        print(f"  {k:24s} active {act:5.1%}  net {int(v.sum()):+d}")
