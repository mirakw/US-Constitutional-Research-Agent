"""
CourtListener API Client
Handles searching and retrieving case law from the Free Law Project's CourtListener API.
Docs: https://www.courtlistener.com/api/rest/v3/
"""

import requests
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://www.courtlistener.com/api/rest/v4"

# Federal courts for constitutional law research
FEDERAL_COURTS = [
    "scotus",
    "ca1", "ca2", "ca3", "ca4", "ca5", "ca6",
    "ca7", "ca8", "ca9", "ca10", "ca11", "cadc", "cafc"
]


class CourtListenerClient:
    """Client for the CourtListener REST API."""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token
        self.session = requests.Session()
        if api_token:
            self.session.headers.update({
                "Authorization": f"Token {api_token}"
            })
        self.session.headers.update({
            "User-Agent": "ConstitutionalLawResearchAgent/1.0"
        })

    def is_configured(self) -> bool:
        """Check if the client has an API token."""
        return bool(self.api_token)

    def search_opinions(self, query: str, court: Optional[str] = None,
                        date_after: Optional[str] = None,
                        date_before: Optional[str] = None,
                        max_results: int = 20) -> list:
        """
        Search for court opinions matching a query.

        Args:
            query: Search terms (e.g., "fourth amendment digital privacy")
            court: Court filter (e.g., "scotus" or "ca9")
            date_after: Filter cases after this date (YYYY-MM-DD)
            date_before: Filter cases before this date (YYYY-MM-DD)
            max_results: Maximum results to return

        Returns:
            List of case dictionaries with metadata and opinion excerpts
        """
        params = {
            "q": query,
            "type": "o",  # opinions
            "order_by": "score desc",
            "format": "json",
        }

        if court:
            params["court"] = court
        else:
            # Default to federal courts for constitutional law
            params["court"] = " ".join(FEDERAL_COURTS)

        if date_after:
            params["filed_after"] = date_after
        if date_before:
            params["filed_before"] = date_before

        try:
            url = f"{BASE_URL}/search/"
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", [])[:max_results]:
                case = self._parse_search_result(item)
                if case:
                    results.append(case)

            logger.info(f"CourtListener search: found {len(results)} results for '{query}'")
            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"CourtListener search error: {e}")
            return []

    def get_opinion(self, opinion_id: int) -> Optional[dict]:
        """
        Fetch a full opinion by its CourtListener ID.

        Args:
            opinion_id: The CourtListener opinion ID

        Returns:
            Dictionary with full opinion text and metadata
        """
        try:
            url = f"{BASE_URL}/opinions/{opinion_id}/"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            return {
                "id": data.get("id"),
                "html": data.get("html_with_citations", data.get("html", "")),
                "plain_text": data.get("plain_text", ""),
                "type": data.get("type", ""),
                "author": data.get("author_str", ""),
                "per_curiam": data.get("per_curiam", False),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"CourtListener opinion fetch error: {e}")
            return None

    def get_cluster(self, cluster_id: int) -> Optional[dict]:
        """
        Fetch case metadata (cluster) by ID.
        A cluster groups all opinions for a single case.

        Args:
            cluster_id: The CourtListener cluster ID

        Returns:
            Dictionary with case metadata
        """
        try:
            url = f"{BASE_URL}/clusters/{cluster_id}/"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            return {
                "id": data.get("id"),
                "case_name": data.get("case_name", ""),
                "date_filed": data.get("date_filed", ""),
                "court": data.get("court", ""),
                "citations": data.get("citations", []),
                "judges": data.get("judges", ""),
                "precedential_status": data.get("precedential_status", ""),
                "syllabus": data.get("syllabus", ""),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"CourtListener cluster fetch error: {e}")
            return None

    def lookup_citation(self, text: str) -> list:
        """
        Extract and resolve citations from a block of text.
        Uses CourtListener's citation-lookup API.

        Args:
            text: Text containing legal citations

        Returns:
            List of resolved citations with case info
        """
        try:
            url = f"{BASE_URL}/citation-lookup/"
            response = self.session.post(url, data={"text": text}, timeout=30)
            response.raise_for_status()
            data = response.json()

            citations = []
            for item in data:
                if item.get("status") == 200 and item.get("clusters"):
                    citations.append({
                        "citation": item.get("citation", ""),
                        "normalized": item.get("normalized_citations", []),
                        "clusters": item.get("clusters", [])
                    })

            return citations

        except requests.exceptions.RequestException as e:
            logger.error(f"CourtListener citation lookup error: {e}")
            return []

    def _parse_search_result(self, item: dict) -> Optional[dict]:
        """Parse a search result into a standardized case dictionary."""
        try:
            # Extract cluster ID from the absolute_url
            cluster_url = item.get("cluster_id") or item.get("cluster", "")
            cluster_id = None
            if isinstance(cluster_url, str) and "/" in cluster_url:
                parts = cluster_url.strip("/").split("/")
                cluster_id = parts[-1] if parts else None
            elif isinstance(cluster_url, int):
                cluster_id = cluster_url

            return {
                "source": "courtlistener",
                "case_name": item.get("caseName", item.get("case_name", "Unknown")),
                "date_filed": item.get("dateFiled", item.get("date_filed", "")),
                "court": item.get("court", item.get("court_id", "")),
                "court_citation_string": item.get("court_citation_string", ""),
                "citation": self._extract_citation(item),
                "snippet": item.get("snippet", ""),
                "judges": item.get("judge", ""),
                "opinion_id": item.get("id"),
                "cluster_id": cluster_id,
                "absolute_url": item.get("absolute_url", ""),
                "status": item.get("status", ""),
                "relevance_score": item.get("score", 0),
            }
        except Exception as e:
            logger.warning(f"Error parsing search result: {e}")
            return None

    def _extract_citation(self, item: dict) -> str:
        """Extract the best citation string from a search result."""
        # Try citation field directly
        citation = item.get("citation", [])
        if isinstance(citation, list) and citation:
            return citation[0]
        if isinstance(citation, str) and citation:
            return citation

        # Try lexisCite or neutralCite
        for field in ["lexisCite", "neutralCite", "suitNature"]:
            val = item.get(field, "")
            if val:
                return val

        # Build from case name and court
        name = item.get("caseName", "")
        court = item.get("court_citation_string", "")
        date = item.get("dateFiled", "")
        if name:
            return f"{name} ({court} {date[:4]})" if court else name

        return "Citation unavailable"
