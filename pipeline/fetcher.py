"""
Case Fetcher (Step 2)
Takes the specific case names and statutes identified by Gemini
and fetches real data from CourtListener, SCOTUS, and Congress.gov.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class CaseFetcher:
    """Fetches real legal data for specific cases and statutes."""

    def __init__(self, courtlistener_client, congress_client, scotus_client):
        self.cl = courtlistener_client
        self.congress = congress_client
        self.scotus = scotus_client

    def fetch(self, case_names: list, statute_names: list,
              search_queries: list = None) -> dict:
        """
        Fetch real data for the cases and statutes Gemini identified.

        Args:
            case_names: ["Harlow v. Fitzgerald", "Pearson v. Callahan", ...]
            statute_names: ["42 U.S.C. § 1983", ...]
            search_queries: ["qualified immunity excessive force", ...]

        Returns:
            {
                "cases": [list of case dicts with real data],
                "statutes": [list of statute dicts with real data]
            }
        """
        results = {"cases": [], "statutes": []}

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}

            # Search for each specific case by name
            for name in case_names:
                futures[executor.submit(self._fetch_case, name)] = f"case:{name}"

            # Search for statutes
            for statute in statute_names:
                futures[executor.submit(self._fetch_statute, statute)] = f"statute:{statute}"

            # Also run broader search queries for cases Gemini might have missed
            for query in (search_queries or []):
                futures[executor.submit(self._search_cases, query)] = f"search:{query}"

            # Collect results
            for future in as_completed(futures):
                label = futures[future]
                try:
                    data = future.result()
                    if data is None:
                        continue
                    if label.startswith("case:") or label.startswith("search:"):
                        if isinstance(data, list):
                            results["cases"].extend(data)
                        else:
                            results["cases"].append(data)
                    elif label.startswith("statute:"):
                        if isinstance(data, list):
                            results["statutes"].extend(data)
                        else:
                            results["statutes"].append(data)
                except Exception as e:
                    logger.error(f"Fetch error for {label}: {e}")

        # Deduplicate cases by name
        results["cases"] = self._deduplicate(results["cases"])

        # Also check SCOTUS landmark database
        for name in case_names:
            landmark = self._check_landmark(name)
            if landmark and not self._already_have(landmark, results["cases"]):
                results["cases"].append(landmark)

        return results

    def _fetch_case(self, case_name: str) -> dict:
        """Search CourtListener for a specific case by name."""
        try:
            # Search by case name
            results = self.cl.search_opinions(
                query=f'"{case_name}"',
                max_results=3
            )

            if results:
                # Return the best match
                best = self._best_match(case_name, results)
                if best:
                    return best

            # Try without quotes (looser search)
            results = self.cl.search_opinions(
                query=case_name,
                max_results=3
            )

            if results:
                return self._best_match(case_name, results)

            return None

        except Exception as e:
            logger.error(f"Fetch case error for '{case_name}': {e}")
            return None

    def _search_cases(self, query: str) -> list:
        """Run a broader search query on CourtListener."""
        try:
            results = self.cl.search_opinions(query=query, max_results=5)
            return results
        except Exception as e:
            logger.error(f"Search error for '{query}': {e}")
            return []

    def _fetch_statute(self, statute_name: str) -> dict:
        """Search Congress.gov for a specific statute."""
        try:
            # Clean up statute name for search
            search_term = statute_name.replace("§", "").replace("U.S.C.", "").strip()
            results = self.congress.search_bills(search_term, max_results=3)

            if results:
                return results[0]
            return None

        except Exception as e:
            logger.error(f"Fetch statute error for '{statute_name}': {e}")
            return None

    def _check_landmark(self, case_name: str) -> dict:
        """Check our built-in SCOTUS landmark database."""
        # Use the SCOTUS client's topic search to find landmarks
        # We search by partial case name match
        name_lower = case_name.lower()
        landmarks = self.scotus.search_by_topic(name_lower, max_results=3)

        for landmark in landmarks:
            landmark_name = landmark.get("case_name", "").lower()
            if self._names_match(name_lower, landmark_name):
                landmark["source"] = "scotus_landmark"
                landmark["is_landmark"] = True
                return landmark

        return None

    def _best_match(self, target_name: str, results: list) -> dict:
        """Find the best matching case from search results."""
        target = target_name.lower().strip()

        # First: exact match
        for r in results:
            if self._names_match(target, r.get("case_name", "").lower()):
                return r

        # Second: partial match (both parties appear)
        parts = re.split(r'\s+v\.?\s+', target)
        if len(parts) == 2:
            for r in results:
                name = r.get("case_name", "").lower()
                if parts[0].strip()[:8] in name and parts[1].strip()[:8] in name:
                    return r

        # Third: just return the top result if it looks reasonable
        if results:
            return results[0]

        return None

    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two case names refer to the same case."""
        # Normalize both
        def normalize(n):
            n = n.lower().strip()
            n = n.replace(" v. ", " v ").replace(" vs. ", " v ")
            n = re.sub(r'[^a-z0-9 ]', '', n)
            return " ".join(n.split())

        n1 = normalize(name1)
        n2 = normalize(name2)

        # Check if one contains the other or they share key words
        if n1 in n2 or n2 in n1:
            return True

        # Check if the party names match
        parts1 = n1.split(" v ")
        parts2 = n2.split(" v ")
        if len(parts1) == 2 and len(parts2) == 2:
            if (parts1[0].strip()[:6] == parts2[0].strip()[:6] and
                    parts1[1].strip()[:6] == parts2[1].strip()[:6]):
                return True

        return False

    def _already_have(self, case: dict, existing: list) -> bool:
        """Check if we already have this case in our results."""
        name = case.get("case_name", "").lower()
        for e in existing:
            if self._names_match(name, e.get("case_name", "").lower()):
                return True
        return False

    def _deduplicate(self, cases: list) -> list:
        """Remove duplicate cases."""
        seen = set()
        unique = []
        for case in cases:
            name = case.get("case_name", "").lower().strip()
            name = re.sub(r'[^a-z0-9 ]', '', name)
            key = " ".join(name.split())[:60]
            if key and key not in seen:
                seen.add(key)
                unique.append(case)
        return unique
