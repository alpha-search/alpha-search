"""GitHub repository statistics, commit activity, contributor metrics, and developer engagement data for open-source projects. (stub).

GitHub -- developer activity metrics for open-source projects.

To activate this source:
    1. Get API key at https://github.com/settings/tokens
    2. Set GITHUB_TOKEN env var
    3. pip install PyGithub
    4. Implement activity tracking

References:
    - https://pygithub.readthedocs.io/
"""

from __future__ import annotations

import logging

import pandas as pd

from alpha_search.data_sources.base import DataSource, SourceMeta

logger = logging.getLogger(__name__)


class GitHubActivitySource(DataSource):
    """GitHub -- developer activity and repository metrics.

    Status: **stub** -- implement the methods below to activate.
    """

    meta = SourceMeta(
        name="github_activity",
        category="alternative",
        description="GitHub -- developer activity metrics for open-source projects.",
        requires_api_key=False,
        free_tier=True,
        rate_limit="5000 requests/hour",
        data_types=["activity", "commits", "contributors", "issues"],
        coverage="global",
        homepage="https://github.com",
        docs_url="https://pygithub.readthedocs.io/",
        install_cmd="pip install PyGithub",
        status="stub",
    )

    def is_available(self) -> bool:
        """Return ``False`` -- this source is a stub and not yet implemented."""
        return False

    def fetch_ohlcv(
        self, symbol: str, start: str, end: str, interval: str = "1d",
    ) -> pd.DataFrame:
        """Not implemented -- activate by overriding this method."""
        raise NotImplementedError(
            "GitHubActivitySource is a stub. To activate it:\n"
            "1. Get API key at https://github.com/settings/tokens\n"
            "2. Set GITHUB_TOKEN environment variable\n"
            "3. pip install PyGithub\n"
            "4. Implement activity tracking using github.Github"
        )
