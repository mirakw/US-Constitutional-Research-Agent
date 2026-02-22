"""
Congress.gov API Client
Handles searching and retrieving federal legislation, bill text,
and legislative history from the Library of Congress API.
Docs: https://github.com/LibraryOfCongress/api.congress.gov
"""

import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.congress.gov/v3"


class CongressGovClient:
    """Client for the Congress.gov REST API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ConstitutionalLawResearchAgent/1.0",
            "Accept": "application/json"
        })

    def is_configured(self) -> bool:
        """Check if the client has an API key."""
        return bool(self.api_key)

    def search_bills(self, query: str, congress: Optional[int] = None,
                     max_results: int = 10) -> list:
        """
        Search for legislation by keyword.

        Args:
            query: Search terms (e.g., "digital privacy fourth amendment")
            congress: Specific congress number (e.g., 118 for 118th Congress)
            max_results: Maximum results to return

        Returns:
            List of bill dictionaries with metadata
        """
        if not self.api_key:
            logger.warning("Congress.gov API key not configured")
            return []

        params = {
            "api_key": self.api_key,
            "query": query,
            "limit": min(max_results, 250),
            "format": "json",
            "sort": "relevance"
        }

        try:
            if congress:
                url = f"{BASE_URL}/bill/{congress}"
            else:
                url = f"{BASE_URL}/bill"

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = []
            bills = data.get("bills", [])
            for bill in bills[:max_results]:
                parsed = self._parse_bill(bill)
                if parsed:
                    results.append(parsed)

            logger.info(f"Congress.gov search: found {len(results)} bills for '{query}'")
            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"Congress.gov search error: {e}")
            return []

    def get_bill_details(self, congress: int, bill_type: str, bill_number: int) -> Optional[dict]:
        """
        Fetch detailed information about a specific bill.

        Args:
            congress: Congress number (e.g., 118)
            bill_type: Type of bill (hr, s, hjres, sjres, etc.)
            bill_number: Bill number

        Returns:
            Dictionary with bill details
        """
        if not self.api_key:
            return None

        try:
            url = f"{BASE_URL}/bill/{congress}/{bill_type}/{bill_number}"
            params = {"api_key": self.api_key, "format": "json"}
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            bill = data.get("bill", {})
            return {
                "source": "congress_gov",
                "title": bill.get("title", ""),
                "number": f"{bill_type.upper()} {bill_number}",
                "congress": congress,
                "introduced_date": bill.get("introducedDate", ""),
                "latest_action": bill.get("latestAction", {}).get("text", ""),
                "latest_action_date": bill.get("latestAction", {}).get("actionDate", ""),
                "policy_area": bill.get("policyArea", {}).get("name", ""),
                "sponsors": [s.get("fullName", "") for s in bill.get("sponsors", [])],
                "committees": bill.get("committees", {}).get("url", ""),
                "summary_url": bill.get("summaries", {}).get("url", ""),
                "text_url": bill.get("textVersions", {}).get("url", ""),
                "url": bill.get("url", ""),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Congress.gov bill details error: {e}")
            return None

    def get_bill_text(self, congress: int, bill_type: str, bill_number: int) -> Optional[str]:
        """
        Fetch the full text of a bill.

        Args:
            congress: Congress number
            bill_type: Type of bill
            bill_number: Bill number

        Returns:
            Bill text as string, or None
        """
        if not self.api_key:
            return None

        try:
            url = f"{BASE_URL}/bill/{congress}/{bill_type}/{bill_number}/text"
            params = {"api_key": self.api_key, "format": "json"}
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            text_versions = data.get("textVersions", [])
            if text_versions:
                # Get the most recent version
                latest = text_versions[0]
                formats = latest.get("formats", [])
                # Prefer plain text
                for fmt in formats:
                    if fmt.get("type") == "Formatted Text":
                        text_url = fmt.get("url", "")
                        if text_url:
                            text_response = self.session.get(text_url, timeout=30)
                            return text_response.text

            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Congress.gov bill text error: {e}")
            return None

    def get_bill_actions(self, congress: int, bill_type: str, bill_number: int) -> list:
        """
        Fetch the legislative history (actions) for a bill.

        Args:
            congress: Congress number
            bill_type: Type of bill
            bill_number: Bill number

        Returns:
            List of action dictionaries (legislative timeline)
        """
        if not self.api_key:
            return []

        try:
            url = f"{BASE_URL}/bill/{congress}/{bill_type}/{bill_number}/actions"
            params = {"api_key": self.api_key, "format": "json"}
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            actions = []
            for action in data.get("actions", []):
                actions.append({
                    "date": action.get("actionDate", ""),
                    "text": action.get("text", ""),
                    "type": action.get("type", ""),
                    "chamber": action.get("actionCode", ""),
                })

            return actions

        except requests.exceptions.RequestException as e:
            logger.error(f"Congress.gov bill actions error: {e}")
            return []

    def search_statutes_by_topic(self, topic: str, max_results: int = 5) -> list:
        """
        Search for statutes and laws related to a constitutional topic.
        Searches across recent congresses for relevant legislation.

        Args:
            topic: Legal topic to search (e.g., "surveillance privacy")
            max_results: Maximum results to return

        Returns:
            List of relevant statute/bill dictionaries
        """
        all_results = []

        # Search across recent congresses (current and previous few)
        for congress_num in [118, 117, 116]:
            results = self.search_bills(topic, congress=congress_num, max_results=max_results)
            all_results.extend(results)

            if len(all_results) >= max_results:
                break

        return all_results[:max_results]

    def _parse_bill(self, bill: dict) -> Optional[dict]:
        """Parse a bill search result into a standardized dictionary."""
        try:
            return {
                "source": "congress_gov",
                "title": bill.get("title", ""),
                "number": bill.get("number", ""),
                "type": bill.get("type", ""),
                "congress": bill.get("congress", ""),
                "introduced_date": bill.get("introducedDate", ""),
                "latest_action": bill.get("latestAction", {}).get("text", "") if isinstance(bill.get("latestAction"), dict) else "",
                "latest_action_date": bill.get("latestAction", {}).get("actionDate", "") if isinstance(bill.get("latestAction"), dict) else "",
                "policy_area": bill.get("policyArea", {}).get("name", "") if isinstance(bill.get("policyArea"), dict) else "",
                "url": bill.get("url", ""),
            }
        except Exception as e:
            logger.warning(f"Error parsing bill: {e}")
            return None
