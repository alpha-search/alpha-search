"""Stock universe definitions for Alpha Search research pipelines.

This module provides the :class:`Universe` dataclass and a registry of
predefined stock universes covering US large-cap, US tech, US financials,
and Indian (NSE) names.  New universes can be registered at runtime by
inserting into :data:`UNIVERSE_REGISTRY`.

Typical usage::

    from alpha_search.research.universes import get_universe, US_LARGE_CAP
    universe = get_universe("us_large_cap")
    print(universe.tickers)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Universe dataclass
# ---------------------------------------------------------------------------

@dataclass
class Universe:
    """A named universe of tickers with descriptive metadata.

    Attributes
    ----------
    name:
        Machine-friendly identifier (e.g. ``"us_large_cap"``).
    tickers:
        Ordered list of ticker symbols.  Duplicate entries are preserved
        on construction but may be deduplicated via :meth:`unique`.
    description:
        Human-friendly summary of what this universe covers.
    asset_class:
        Broad asset class label (e.g. ``"equity"``, ``"crypto"``).
    region:
        Geographic region code (e.g. ``"US"``, ``"IN"``).
    tags:
        Optional list of arbitrary tags for filtering / grouping.
    meta:
        Free-form dictionary for extra metadata (e.g. creation date,
        revision notes, data-vendor mappings).
    """

    name: str
    tickers: List[str]
    description: str = ""
    asset_class: str = "equity"
    region: str = "US"
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    # -- dict round-trip ---------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary suitable for JSON / YAML storage.

        Returns
        -------
        dict
            Dictionary with keys: ``name``, ``tickers``, ``description``,
            ``asset_class``, ``region``, ``tags``, ``meta``.
        """
        return {
            "name": self.name,
            "tickers": list(self.tickers),
            "description": self.description,
            "asset_class": self.asset_class,
            "region": self.region,
            "tags": list(self.tags),
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Universe:
        """Deserialize from a dictionary produced by :meth:`to_dict`.

        Parameters
        ----------
        d:
            Dictionary with keys matching the dataclass fields.

        Returns
        -------
        Universe
            A new ``Universe`` instance.

        Raises
        ------
        KeyError
            If ``name`` or ``tickers`` keys are missing.
        """
        required_keys = {"name", "tickers"}
        missing = required_keys - d.keys()
        if missing:
            raise KeyError(f"Universe dict missing required keys: {missing}")
        return cls(
            name=d["name"],
            tickers=list(d["tickers"]),
            description=d.get("description", ""),
            asset_class=d.get("asset_class", "equity"),
            region=d.get("region", "US"),
            tags=list(d.get("tags", [])),
            meta=dict(d.get("meta", {})),
        )

    # -- helpers -----------------------------------------------------------

    def unique(self) -> Universe:
        """Return a new Universe with duplicate tickers removed.

        Returns
        -------
        Universe
            A new instance; the original is left untouched.
        """
        seen: set[str] = set()
        deduped: list[str] = []
        for t in self.tickers:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        return Universe(
            name=self.name,
            tickers=deduped,
            description=self.description,
            asset_class=self.asset_class,
            region=self.region,
            tags=list(self.tags),
            meta=dict(self.meta),
        )

    def intersection(self, other: Universe) -> Universe:
        """Return the ticker intersection with *other*.

        Parameters
        ----------
        other:
            Another ``Universe`` to intersect with.

        Returns
        -------
        Universe
            A new instance containing only tickers present in both
            universes.  The *name* and *description* are updated to
            reflect the operation.
        """
        common = list(set(self.tickers) & set(other.tickers))
        return Universe(
            name=f"{self.name}_intersect_{other.name}",
            tickers=common,
            description=(
                f"Intersection of {self.name} ({len(self.tickers)}) "
                f"and {other.name} ({len(other.tickers)}) -> {len(common)}"
            ),
            asset_class=self.asset_class,
            region=self.region,
        )

    def union(self, other: Universe) -> Universe:
        """Return the ticker union with *other*.

        Parameters
        ----------
        other:
            Another ``Universe`` to union with.

        Returns
        -------
        Universe
            A new instance containing tickers from both universes
            without duplication.
        """
        combined = list(dict.fromkeys(self.tickers + other.tickers))
        return Universe(
            name=f"{self.name}_union_{other.name}",
            tickers=combined,
            description=(
                f"Union of {self.name} ({len(self.tickers)}) "
                f"and {other.name} ({len(other.tickers)}) -> {len(combined)}"
            ),
            asset_class=self.asset_class,
            region=self.region,
        )

    def filter_by_region(self, region: str) -> Universe:
        """Return a new Universe scoped to *region* (case-insensitive).

        This is primarily useful when the ticker list is heterogeneous
        (e.g. after a union operation).  Tickers themselves are not
        validated against any exchange master.

        Parameters
        ----------
        region:
            Two-letter region code such as ``"US"`` or ``"IN"``.

        Returns
        -------
        Universe
            A new instance with the ``region`` field updated.
        """
        return Universe(
            name=f"{self.name}_{region.lower()}",
            tickers=list(self.tickers),
            description=f"{self.description} (region={region})",
            asset_class=self.asset_class,
            region=region.upper(),
        )

    def __len__(self) -> int:
        return len(self.tickers)

    def __iter__(self):
        return iter(self.tickers)

    def __contains__(self, ticker: str) -> bool:
        return ticker in self.tickers

    def __repr__(self) -> str:
        return (
            f"Universe(name={self.name!r}, tickers=<{len(self.tickers)} items>, "
            f"region={self.region!r})"
        )


# ---------------------------------------------------------------------------
# Predefined universes
# ---------------------------------------------------------------------------

US_LARGE_CAP = Universe(
    name="us_large_cap",
    tickers=[
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META",
        "JPM", "XOM", "UNH", "TSLA", "SPY", "QQQ",
    ],
    description="Top US large-cap stocks + broad ETFs",
    asset_class="equity",
    region="US",
    tags=["us", "large-cap", "liquid"],
)

US_TECH = Universe(
    name="us_tech",
    tickers=[
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META",
        "NFLX", "CRM", "ADBE", "TSLA", "AVGO", "QQQ",
    ],
    description="US technology sector heavyweights",
    asset_class="equity",
    region="US",
    tags=["us", "technology", "growth"],
)

US_FINANCIALS = Universe(
    name="us_financials",
    tickers=[
        "JPM", "BAC", "WFC", "GS", "MS", "C",
        "BLK", "SPGI", "AXP", "SCHW",
    ],
    description="US financial sector bellwethers",
    asset_class="equity",
    region="US",
    tags=["us", "financials", "value"],
)

INDIA_NIFTY = Universe(
    name="india_nifty",
    tickers=[
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
        "ICICIBANK.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    ],
    description="Top 10 Nifty 50 constituents (NSE)",
    asset_class="equity",
    region="IN",
    tags=["india", "nifty", "large-cap"],
)

# Convenience singleton — all available tickers across every predefined universe
ALL_PREDEFINED = Universe(
    name="all_predefined",
    tickers=list(
        dict.fromkeys(
            US_LARGE_CAP.tickers
            + US_TECH.tickers
            + US_FINANCIALS.tickers
            + INDIA_NIFTY.tickers
        )
    ),
    description="Union of every predefined universe (deduplicated)",
    asset_class="equity",
    region="US",
    tags=["composite"],
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

UNIVERSE_REGISTRY: Dict[str, Universe] = {
    US_LARGE_CAP.name: US_LARGE_CAP,
    US_TECH.name: US_TECH,
    US_FINANCIALS.name: US_FINANCIALS,
    INDIA_NIFTY.name: INDIA_NIFTY,
    ALL_PREDEFINED.name: ALL_PREDEFINED,
}


def get_universe(name: str) -> Universe:
    """Look up a :class:`Universe` by its registered name.

    Parameters
    ----------
    name:
        The ``name`` attribute of a predefined universe (e.g.
        ``"us_large_cap"``) or any key present in
        :data:`UNIVERSE_REGISTRY`.

    Returns
    -------
    Universe
        The matching universe instance.

    Raises
    ------
    KeyError
        If *name* is not found in :data:`UNIVERSE_REGISTRY`.
    """
    try:
        return UNIVERSE_REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(UNIVERSE_REGISTRY.keys()))
        raise KeyError(
            f"Universe '{name}' not found. Available: [{available}]"
        ) from exc


def register_universe(universe: Universe, *, allow_overwrite: bool = False) -> None:
    """Add a custom universe to :data:`UNIVERSE_REGISTRY`.

    Parameters
    ----------
    universe:
        The ``Universe`` instance to register.
    allow_overwrite:
        If ``False`` (default), raises :exc:`ValueError` when a
        universe with the same name already exists.

    Raises
    ------
    ValueError
        If *allow_overwrite* is ``False`` and *universe.name* already
        exists in the registry.
    """
    if universe.name in UNIVERSE_REGISTRY and not allow_overwrite:
        raise ValueError(
            f"Universe '{universe.name}' already registered. "
            "Set allow_overwrite=True to replace."
        )
    UNIVERSE_REGISTRY[universe.name] = universe
    logger.info("Registered universe '%s' (%d tickers)", universe.name, len(universe.tickers))


def list_universes(
    *,
    region: Optional[str] = None,
    asset_class: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[str]:
    """Return the names of universes matching optional filters.

    Parameters
    ----------
    region:
        Filter by exact ``region`` match (case-insensitive).
    asset_class:
        Filter by exact ``asset_class`` match (case-insensitive).
    tag:
        Filter by tag presence (case-insensitive).

    Returns
    -------
    List[str]
        Sorted list of matching universe names.
    """
    results: list[str] = []
    for name, universe in UNIVERSE_REGISTRY.items():
        if region is not None and universe.region.upper() != region.upper():
            continue
        if asset_class is not None and universe.asset_class.upper() != asset_class.upper():
            continue
        if tag is not None and tag.lower() not in [t.lower() for t in universe.tags]:
            continue
        results.append(name)
    return sorted(results)


def build_custom_universe(
    name: str,
    ticker_source: List[str],
    *,
    description: str = "",
    asset_class: str = "equity",
    region: str = "US",
    register: bool = True,
) -> Universe:
    """Convenience factory for one-off research universes.

    Parameters
    ----------
    name:
        Unique identifier for the new universe.
    ticker_source:
        Raw list of ticker strings (duplicates are removed).
    description:
        Optional human-friendly description.
    asset_class:
        Asset-class label.
    region:
        Region code.
    register:
        If ``True`` (default), insert the new universe into
        :data:`UNIVERSE_REGISTRY`.

    Returns
    -------
    Universe
        The newly created (deduplicated) instance.
    """
    deduped = list(dict.fromkeys(ticker_source))
    universe = Universe(
        name=name,
        tickers=deduped,
        description=description or f"Custom universe ({len(deduped)} tickers)",
        asset_class=asset_class,
        region=region,
    )
    if register:
        register_universe(universe, allow_overwrite=True)
    return universe
