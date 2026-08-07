"""
Stage 3 — BACKTEST
==================
Vectorized, next-bar-execution backtester + honest statistics.

Execution model
---------------
A signal value at bar t is the position to HOLD INTO bar t+1. We therefore
execute on the *next* bar: `pos_exec = target.shift(1)`. The P&L attributed to
bar t is `pos_exec[t] * bar_return[t]`. `bar_return` is close-to-close and is
NaN'd (→0) at every session open, so no overnight return is ever earned — this
also enforces "flat by end of day". `test_backtest.py` asserts the no-lookahead
property mechanically.

Costs: 1 bp commission + 2 bp slippage = 3 bp per side, charged on |Δposition|.
A zero-cost variant is reported alongside so cost drag is visible.

Statistics for a small-sample, many-strategy search:
  * total configuration count,
  * Deflated Sharpe Ratio (Bailey & López de Prado) for the winner,
  * 70/30 train/hold-out split with BOTH Sharpes reported,
  * a 500-iteration permutation test giving the winner's Sharpe percentile
    in the null distribution.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

BARS_PER_YEAR = 252 * 78            # 5-minute RTH bars
COMMISSION_BP = 1.0
SLIPPAGE_BP = 2.0
COST_PER_SIDE = (COMMISSION_BP + SLIPPAGE_BP) / 1e4     # 3 bp as a fraction


# --------------------------------------------------------------------------- #
# Core P&L
# --------------------------------------------------------------------------- #
def bar_returns(px: pd.DataFrame) -> pd.Series:
    """Close-to-close simple returns; 0 at each session open (no overnight)."""
    r = px["Close"].pct_change()
    first = px.index.normalize().to_series(index=px.index).ne(
        px.index.normalize().to_series(index=px.index).shift())
    r[first.values] = 0.0
    return r.fillna(0.0)


def enforce_eod_flat(target: pd.Series, px: pd.DataFrame) -> pd.Series:
    """Force the target position to 0 on the last bar of each session."""
    last = px.index.normalize().to_series(index=px.index).ne(
        px.index.normalize().to_series(index=px.index).shift(-1))
    t = target.copy()
    t[last.values] = 0.0
    return t


def run_backtest(target: pd.Series, px: pd.DataFrame, costs: bool = True) -> pd.Series:
    """Return the per-bar NET (or gross) strategy return series (next-bar exec)."""
    target = enforce_eod_flat(target.clip(-1, 1), px)
    pos_exec = target.shift(1).fillna(0.0)               # NEXT-BAR execution
    gross = pos_exec * bar_returns(px)
    if not costs:
        return gross
    turnover = pos_exec.diff().abs().fillna(pos_exec.abs())
    return gross - turnover * COST_PER_SIDE


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def _annualized_sharpe(r: pd.Series) -> float:
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(BARS_PER_YEAR)) if sd > 0 else 0.0


def _sortino(r: pd.Series) -> float:
    dn = r[r < 0].std(ddof=1)
    return float(r.mean() / dn * np.sqrt(BARS_PER_YEAR)) if dn > 0 else 0.0


def _max_drawdown(r: pd.Series) -> float:
    eq = (1 + r).cumprod()
    dd = eq / eq.cummax() - 1.0
    return float(dd.min())


def trade_stats(target: pd.Series, px: pd.DataFrame, ret: pd.Series) -> dict:
    """Per-trade decomposition: count, hit rate, avg win/loss, holding, PF."""
    pos = enforce_eod_flat(target.clip(-1, 1), px).shift(1).fillna(0.0)
    change = pos.ne(pos.shift()).cumsum()                 # trade/segment id
    seg = pd.DataFrame({"pos": pos, "ret": ret, "seg": change})
    seg = seg[seg["pos"] != 0]
    if seg.empty:
        return dict(n_trades=0, hit_rate=np.nan, avg_win=np.nan, avg_loss=np.nan,
                    profit_factor=np.nan, avg_hold_bars=np.nan)
    g = seg.groupby("seg")
    pnl = g["ret"].sum()
    hold = g.size()
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    pf = float(wins.sum() / -losses.sum()) if losses.sum() != 0 else np.inf
    return dict(
        n_trades=int(len(pnl)),
        hit_rate=float((pnl > 0).mean()),
        avg_win=float(wins.mean()) if len(wins) else 0.0,
        avg_loss=float(losses.mean()) if len(losses) else 0.0,
        profit_factor=pf,
        avg_hold_bars=float(hold.mean()),
    )


def metrics(target: pd.Series, px: pd.DataFrame, costs: bool = True) -> dict:
    ret = run_backtest(target, px, costs=costs)
    pos_exec = enforce_eod_flat(target.clip(-1, 1), px).shift(1).fillna(0.0)
    n_days = px.index.normalize().nunique()
    turnover = pos_exec.diff().abs().fillna(pos_exec.abs()).sum()
    ts = trade_stats(target, px, ret)
    m = dict(
        sharpe=_annualized_sharpe(ret),
        sortino=_sortino(ret),
        max_dd=_max_drawdown(ret),
        turnover=float(turnover),
        trades_per_day=ts["n_trades"] / n_days if n_days else 0.0,
        total_return=float((1 + ret).prod() - 1),
        **ts,
    )
    return m


# --------------------------------------------------------------------------- #
# Multiple-testing statistics
# --------------------------------------------------------------------------- #
def deflated_sharpe(winner_ret: pd.Series, all_sharpes_annual: np.ndarray) -> dict:
    """
    Deflated Sharpe Ratio (Bailey & López de Prado 2014).
    Deflates the winner's Sharpe by the expected maximum Sharpe attainable from
    K independent trials of zero true skill, accounting for return skew/kurtosis
    and the sample length T.
    """
    r = winner_ret.values
    T = len(r)
    sr = r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else 0.0     # per-bar SR
    sk = float(stats.skew(r))
    ku = float(stats.kurtosis(r, fisher=False))                    # non-excess
    K = len(all_sharpes_annual)

    # variance of the (per-bar) Sharpes across trials
    sr_trials = all_sharpes_annual / np.sqrt(BARS_PER_YEAR)
    V = np.var(sr_trials, ddof=1) if K > 1 else 1e-6
    gamma = 0.5772156649
    z1 = stats.norm.ppf(1 - 1.0 / K)
    z2 = stats.norm.ppf(1 - 1.0 / (K * np.e))
    sr0 = np.sqrt(V) * ((1 - gamma) * z1 + gamma * z2)             # expected max SR under null

    denom = np.sqrt(1 - sk * sr + (ku - 1) / 4.0 * sr ** 2)
    dsr = stats.norm.cdf((sr - sr0) * np.sqrt(T - 1) / denom) if denom > 0 else np.nan
    return dict(
        sr_annual=float(sr * np.sqrt(BARS_PER_YEAR)),
        sr0_annual=float(sr0 * np.sqrt(BARS_PER_YEAR)),
        expected_max_sharpe_from_luck=float(sr0 * np.sqrt(BARS_PER_YEAR)),
        deflated_sharpe_prob=float(dsr),
        n_trials=int(K),
        skew=sk, kurtosis=ku, T=int(T),
    )


def permutation_test(target: pd.Series, px: pd.DataFrame, n_iter: int = 500,
                     seed: int = 7) -> dict:
    """
    Permutation null: keep the strategy's positions, shuffle the bar returns
    (destroying any real timing edge), recompute annualized Sharpe n_iter times.
    Report where the actual Sharpe sits in that null distribution.
    """
    rng = np.random.default_rng(seed)
    pos_exec = enforce_eod_flat(target.clip(-1, 1), px).shift(1).fillna(0.0).values
    br = bar_returns(px).values
    actual = _annualized_sharpe(pd.Series(pos_exec * br))
    null = np.empty(n_iter)
    for i in range(n_iter):
        perm = rng.permutation(br)
        s = (pos_exec * perm)
        sd = s.std(ddof=1)
        null[i] = (s.mean() / sd * np.sqrt(BARS_PER_YEAR)) if sd > 0 else 0.0
    pval = float((null >= actual).mean())
    return dict(
        actual_sharpe=float(actual),
        null_mean=float(null.mean()),
        null_p95=float(np.percentile(null, 95)),
        percentile=float((null < actual).mean() * 100),
        p_value=pval,
    )


# --------------------------------------------------------------------------- #
# Leaderboard driver
# --------------------------------------------------------------------------- #
def split_index(px: pd.DataFrame, frac: float = 0.70):
    days = px.index.normalize().unique()
    cut = days[int(len(days) * frac)]
    is_mask = px.index.normalize() < cut
    return is_mask, ~is_mask, cut


def build_leaderboard(registry: dict[str, pd.Series], px: pd.DataFrame) -> pd.DataFrame:
    is_mask, oos_mask, cut = split_index(px, 0.70)
    px_is, px_oos = px[is_mask], px[oos_mask]
    rows = []
    for name, tgt in registry.items():
        m_full = metrics(tgt, px, costs=True)
        m_is = metrics(tgt[is_mask], px_is, costs=True)
        m_oos = metrics(tgt[oos_mask], px_oos, costs=True)
        m_nocost = metrics(tgt, px, costs=False)
        rows.append(dict(
            strategy=name,
            sharpe_full=m_full["sharpe"],
            sharpe_is=m_is["sharpe"],
            sharpe_oos=m_oos["sharpe"],
            sharpe_nocost=m_nocost["sharpe"],
            cost_drag=m_nocost["sharpe"] - m_full["sharpe"],
            sortino_oos=m_oos["sortino"],
            max_dd_full=m_full["max_dd"],
            hit_rate=m_full["hit_rate"],
            profit_factor=m_full["profit_factor"],
            trades_per_day=m_full["trades_per_day"],
            avg_hold_bars=m_full["avg_hold_bars"],
            turnover=m_full["turnover"],
        ))
    df = pd.DataFrame(rows).sort_values("sharpe_oos", ascending=False).reset_index(drop=True)
    return df, cut
