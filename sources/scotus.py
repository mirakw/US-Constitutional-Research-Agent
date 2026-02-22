"""
Supreme Court (SCOTUS) Client
Handles fetching recent Supreme Court opinions and docket information
directly from supremecourt.gov.
"""

import requests
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_URL = "https://www.supremecourt.gov"


class SCOTUSClient:
    """Client for accessing Supreme Court data."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ConstitutionalLawResearchAgent/1.0"
        })

    def get_recent_opinions(self, term: Optional[str] = None) -> list:
        """
        Fetch recent Supreme Court opinions.
        SCOTUS publishes opinions on their site as slip opinions.

        Args:
            term: Court term (e.g., "2024" for October Term 2024).
                  Defaults to current term.

        Returns:
            List of opinion metadata dictionaries
        """
        if not term:
            # SCOTUS terms start in October, so current term year
            now = datetime.now()
            term = str(now.year if now.month >= 10 else now.year - 1)

        try:
            # SCOTUS publishes a JSON feed of slip opinions
            url = f"{BASE_URL}/opinions/slipopinion/{term}"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                # Parse the HTML for opinion links
                # Note: SCOTUS doesn't have a formal JSON API,
                # so we work with what's available
                return self._parse_opinions_page(response.text, term)
            else:
                logger.warning(f"SCOTUS opinions page returned {response.status_code}")
                return []

        except requests.exceptions.RequestException as e:
            logger.error(f"SCOTUS opinions fetch error: {e}")
            return []

    def get_oral_arguments(self, term: Optional[str] = None) -> list:
        """
        Fetch oral argument information for a given term.

        Args:
            term: Court term year

        Returns:
            List of oral argument metadata
        """
        if not term:
            now = datetime.now()
            term = str(now.year if now.month >= 10 else now.year - 1)

        try:
            url = f"{BASE_URL}/oral_arguments/argument_audio/{term}"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                return self._parse_arguments_page(response.text, term)
            return []

        except requests.exceptions.RequestException as e:
            logger.error(f"SCOTUS oral arguments fetch error: {e}")
            return []

    def search_by_topic(self, topic: str, max_results: int = 5) -> list:
        """
        Search for SCOTUS opinions related to a topic.
        Since SCOTUS doesn't have a search API, we use CourtListener
        for SCOTUS-specific searches. This method provides a fallback
        using known landmark cases for common constitutional topics.

        Args:
            topic: Legal topic to search
            max_results: Maximum results

        Returns:
            List of relevant SCOTUS case references
        """
        # Map common constitutional topics to landmark cases
        # This serves as a seed/fallback when API search is limited
        topic_lower = topic.lower()
        relevant_cases = []

        for keyword, cases in LANDMARK_CASES.items():
            if keyword in topic_lower:
                relevant_cases.extend(cases)

        return relevant_cases[:max_results]

    def _parse_opinions_page(self, html: str, term: str) -> list:
        """Parse SCOTUS opinions page HTML for case data."""
        # Basic HTML parsing — extract case names and PDF links
        opinions = []
        try:
            # Simple extraction — look for PDF links and case names
            import re
            # Pattern: links to opinion PDFs
            pdf_pattern = r'href="(/opinions/\d+pdf/[^"]+)"'
            name_pattern = r'<td[^>]*>([^<]+)</td>'

            pdf_links = re.findall(pdf_pattern, html)
            for link in pdf_links[:10]:
                opinions.append({
                    "source": "scotus",
                    "term": term,
                    "pdf_url": f"{BASE_URL}{link}",
                    "type": "slip_opinion"
                })

        except Exception as e:
            logger.warning(f"Error parsing SCOTUS HTML: {e}")

        return opinions

    def _parse_arguments_page(self, html: str, term: str) -> list:
        """Parse oral arguments page."""
        arguments = []
        try:
            import re
            link_pattern = r'href="(/oral_arguments/audio/\d+/[^"]+)"'
            links = re.findall(link_pattern, html)
            for link in links[:10]:
                arguments.append({
                    "source": "scotus",
                    "term": term,
                    "audio_url": f"{BASE_URL}{link}",
                    "type": "oral_argument"
                })
        except Exception as e:
            logger.warning(f"Error parsing arguments HTML: {e}")

        return arguments


# Landmark constitutional cases by topic — serves as seed data
# for enriching search results with known important cases
LANDMARK_CASES = {
    "fourth amendment": [
        {"case_name": "Carpenter v. United States", "citation": "585 U.S. 296 (2018)", "topic": "Cell phone location data is protected by 4th Amendment"},
        {"case_name": "Riley v. California", "citation": "573 U.S. 373 (2014)", "topic": "Police must get warrant to search cell phones"},
        {"case_name": "Katz v. United States", "citation": "389 U.S. 347 (1967)", "topic": "Established reasonable expectation of privacy test"},
        {"case_name": "Terry v. Ohio", "citation": "392 U.S. 1 (1968)", "topic": "Stop and frisk standards"},
        {"case_name": "Mapp v. Ohio", "citation": "367 U.S. 643 (1961)", "topic": "Exclusionary rule applies to states"},
    ],
    "first amendment": [
        {"case_name": "Tinker v. Des Moines", "citation": "393 U.S. 503 (1969)", "topic": "Student free speech in schools"},
        {"case_name": "New York Times Co. v. Sullivan", "citation": "376 U.S. 254 (1964)", "topic": "Actual malice standard for public figures"},
        {"case_name": "Brandenburg v. Ohio", "citation": "395 U.S. 444 (1969)", "topic": "Imminent lawless action test"},
        {"case_name": "Citizens United v. FEC", "citation": "558 U.S. 310 (2010)", "topic": "Corporate political speech"},
        {"case_name": "Snyder v. Phelps", "citation": "562 U.S. 443 (2011)", "topic": "Westboro Baptist Church protests protected"},
    ],
    "equal protection": [
        {"case_name": "Brown v. Board of Education", "citation": "347 U.S. 483 (1954)", "topic": "School segregation unconstitutional"},
        {"case_name": "Students for Fair Admissions v. Harvard", "citation": "600 U.S. 181 (2023)", "topic": "Race-conscious admissions unconstitutional"},
        {"case_name": "Obergefell v. Hodges", "citation": "576 U.S. 644 (2015)", "topic": "Same-sex marriage is a fundamental right"},
        {"case_name": "Loving v. Virginia", "citation": "388 U.S. 1 (1967)", "topic": "Interracial marriage bans unconstitutional"},
    ],
    "due process": [
        {"case_name": "Mathews v. Eldridge", "citation": "424 U.S. 319 (1976)", "topic": "Three-factor balancing test for procedural due process"},
        {"case_name": "Gideon v. Wainwright", "citation": "372 U.S. 335 (1963)", "topic": "Right to counsel in criminal cases"},
        {"case_name": "Miranda v. Arizona", "citation": "384 U.S. 436 (1966)", "topic": "Miranda rights required before interrogation"},
        {"case_name": "Roe v. Wade", "citation": "410 U.S. 113 (1973)", "topic": "Substantive due process and privacy (overruled by Dobbs)"},
        {"case_name": "Dobbs v. Jackson", "citation": "597 U.S. 215 (2022)", "topic": "No constitutional right to abortion, overruling Roe"},
    ],
    "qualified immunity": [
        {"case_name": "Harlow v. Fitzgerald", "citation": "457 U.S. 800 (1982)", "topic": "Established qualified immunity doctrine"},
        {"case_name": "Pearson v. Callahan", "citation": "555 U.S. 223 (2009)", "topic": "Courts can skip clearly established analysis"},
        {"case_name": "Kisela v. Hughes", "citation": "584 U.S. 100 (2018)", "topic": "High bar for defeating qualified immunity"},
    ],
    "second amendment": [
        {"case_name": "District of Columbia v. Heller", "citation": "554 U.S. 570 (2008)", "topic": "Individual right to bear arms"},
        {"case_name": "McDonald v. City of Chicago", "citation": "561 U.S. 742 (2010)", "topic": "2nd Amendment applies to states"},
        {"case_name": "New York State Rifle & Pistol Assn. v. Bruen", "citation": "597 U.S. 1 (2022)", "topic": "Text, history, and tradition test for gun laws"},
    ],
    "executive power": [
        {"case_name": "Youngstown Sheet & Tube Co. v. Sawyer", "citation": "343 U.S. 579 (1952)", "topic": "Limits on presidential power framework"},
        {"case_name": "Trump v. Hawaii", "citation": "585 U.S. 667 (2018)", "topic": "Presidential authority over immigration"},
        {"case_name": "Nixon v. United States", "citation": "418 U.S. 683 (1974)", "topic": "Executive privilege is not absolute"},
    ],
    "section 1983": [
        {"case_name": "Monroe v. Pape", "citation": "365 U.S. 167 (1961)", "topic": "Section 1983 applies to state officials acting under color of law"},
        {"case_name": "Monell v. Department of Social Services", "citation": "436 U.S. 658 (1978)", "topic": "Municipal liability under Section 1983"},
        {"case_name": "Graham v. Connor", "citation": "490 U.S. 386 (1989)", "topic": "Objective reasonableness standard for excessive force"},
    ],
    "privacy": [
        {"case_name": "Griswold v. Connecticut", "citation": "381 U.S. 479 (1965)", "topic": "Right to privacy in marital relations"},
        {"case_name": "Carpenter v. United States", "citation": "585 U.S. 296 (2018)", "topic": "Digital privacy and cell phone tracking"},
        {"case_name": "Riley v. California", "citation": "573 U.S. 373 (2014)", "topic": "Cell phone search requires warrant"},
    ],
    "digital": [
        {"case_name": "Carpenter v. United States", "citation": "585 U.S. 296 (2018)", "topic": "Cell-site location information protected"},
        {"case_name": "Riley v. California", "citation": "573 U.S. 373 (2014)", "topic": "Warrantless cell phone search unconstitutional"},
        {"case_name": "United States v. Jones", "citation": "565 U.S. 400 (2012)", "topic": "GPS tracking constitutes a search"},
    ],
}
