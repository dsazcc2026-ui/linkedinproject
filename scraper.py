"""
LinkedIn search results scraper.
"""

import re
import urllib.parse
from dataclasses import dataclass
from browser import LinkedInBrowser


@dataclass
class ProfileResult:
    """A LinkedIn profile from search results."""
    name: str
    url: str
    headline: str | None = None


def parse_search_query(natural_query: str) -> dict:
    """
    Parse a natural language query into search components.

    Example: "Uber Eats engineers who left between 2023-2025"
    Returns: {"company": "Uber Eats", "role": "engineers", "keywords": "Uber Eats engineers"}
    """
    # For now, just use the query as keywords
    # Phase 3 will use Claude for smarter parsing
    return {
        "keywords": natural_query,
        "raw_query": natural_query
    }


def build_search_url(keywords: str, page: int = 1) -> str:
    """Build LinkedIn people search URL."""
    encoded = urllib.parse.quote(keywords)
    url = f"https://www.linkedin.com/search/results/people/?keywords={encoded}"
    if page > 1:
        # LinkedIn uses 10 results per page, origin parameter for pagination
        url += f"&page={page}"
    return url


class LinkedInScraper:
    """Scrapes LinkedIn search results."""

    def __init__(self, browser: LinkedInBrowser):
        self.browser = browser
        self.page = browser.page

    def search(self, query: str, max_pages: int = 1) -> list[ProfileResult]:
        """
        Execute a search and return profile results.

        Args:
            query: Natural language search query
            max_pages: Maximum number of result pages to scrape

        Returns:
            List of ProfileResult objects
        """
        parsed = parse_search_query(query)
        all_results = []

        for page_num in range(1, max_pages + 1):
            print(f"  Scraping page {page_num}...")

            url = build_search_url(parsed["keywords"], page_num)
            self.page.goto(url, timeout=60000)
            self.page.wait_for_load_state("domcontentloaded")

            # Wait for search results to load
            self.page.wait_for_timeout(3000)

            # Save screenshot for debugging
            self.page.screenshot(path="debug_screenshot.png")
            print(f"    (Screenshot saved to debug_screenshot.png)")

            results = self._extract_results()
            if not results:
                print(f"  No results on page {page_num}, stopping.")
                break

            all_results.extend(results)
            print(f"  Found {len(results)} profiles on page {page_num}")

            # Check if there's a next page
            has_next = self._has_next_page()
            print(f"    (Has next page: {has_next})")
            if not has_next:
                break

        return all_results

    def _extract_results(self) -> list[ProfileResult]:
        """Extract profile results from current search results page."""
        results = []
        seen_urls = set()

        # Get all profile links directly
        all_links = self.page.query_selector_all('a[href*="/in/"]')
        print(f"    Debug: Found {len(all_links)} profile links")

        # Debug: find what container holds these links
        if all_links:
            for i, link in enumerate(all_links[:3]):
                try:
                    # Find the nearest container div
                    parent_info = link.evaluate('''el => {
                        let p = el.parentElement;
                        for (let i = 0; i < 5 && p; i++) {
                            if (p.tagName === "DIV" && p.className) {
                                return p.className.substring(0, 80);
                            }
                            p = p.parentElement;
                        }
                        return "no div parent";
                    }''')
                    print(f"    Link {i+1} container: {parent_info}")
                except:
                    pass

        # Process each profile link
        for link in all_links:
            try:
                if not link.is_visible():
                    continue

                href = link.get_attribute("href")
                if not href:
                    continue

                profile_url = self._clean_profile_url(href)
                if not profile_url or profile_url in seen_urls:
                    continue

                # Get link info using JavaScript
                link_info = link.evaluate('''el => {
                    let linkText = el.innerText.trim();

                    // Get bounding box to check position (main results are centered)
                    let rect = el.getBoundingClientRect();
                    let x = rect.left;

                    // Check for "mutual" in nearby text (within 2 parent levels)
                    let isMutual = false;
                    let p = el.parentElement;
                    for (let i = 0; i < 2 && p; i++) {
                        let t = p.innerText || "";
                        let tLower = t.toLowerCase();
                        // Catch both "X and Y are mutual connections" and "X is a mutual connection"
                        if (tLower.includes("mutual") && (t.includes(" and ") || tLower.includes(" is a mutual"))) {
                            isMutual = true;
                            break;
                        }
                        p = p.parentElement;
                    }

                    return {
                        name: linkText,
                        x: x,
                        isMutual: isMutual
                    };
                }''')

                name = link_info.get("name", "")
                is_mutual = link_info.get("isMutual", False)
                x_pos = link_info.get("x", 0)

                # Skip if clearly a mutual connection mention
                if is_mutual:
                    continue

                # Skip if name is empty or too long or too short
                if not name or len(name) > 60 or len(name) < 2:
                    continue

                # Skip common non-name patterns
                if name.lower() in ["view", "message", "connect", "follow", "linkedin member"]:
                    continue

                seen_urls.add(profile_url)

                results.append(ProfileResult(
                    name=name,
                    url=profile_url,
                    headline=None
                ))

            except Exception:
                continue

        # Debug: print what we found
        for r in results:
            print(f"      -> {r.name}")

        return results

    def _clean_profile_url(self, href: str) -> str | None:
        """Extract clean LinkedIn profile URL."""
        # Match /in/username pattern
        match = re.search(r'(/in/[^/?]+)', href)
        if match:
            return f"https://www.linkedin.com{match.group(1)}"
        return None

    def _extract_name(self, link) -> str | None:
        """Extract name from profile link or parent elements."""
        # Try to get text from the link itself
        text = link.inner_text().strip()

        # Filter out non-name text
        if text and len(text) < 100 and not text.startswith("View"):
            # Clean up the name
            name = text.split("\n")[0].strip()
            if name:
                return name

        # Try aria-label
        aria = link.get_attribute("aria-label")
        if aria:
            # aria-label often contains "View X's profile"
            match = re.search(r"View (.+?)['']s profile", aria)
            if match:
                return match.group(1)

        return None

    def _extract_headline(self, element) -> str | None:
        """Try to extract headline/title from nearby elements."""
        try:
            text = element.inner_text()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            # Headline is usually the second non-empty line after name
            if len(lines) >= 2:
                return lines[1][:200]  # Limit length
        except Exception:
            pass
        return None

    def _has_next_page(self) -> bool:
        """Check if there's a next page of results."""
        # Try multiple selectors for the next button
        selectors = [
            'button[aria-label="Next"]',
            'button.artdeco-pagination__button--next',
            'button[aria-label*="Next"]',
            'a[aria-label="Next"]',
        ]

        for selector in selectors:
            next_button = self.page.query_selector(selector)
            if next_button and next_button.is_visible():
                disabled = next_button.get_attribute("disabled")
                if not disabled:
                    return True

        # Also check for pagination numbers - if there's a page 2 link, there's a next page
        page_buttons = self.page.query_selector_all('button[aria-label*="Page"]')
        current_page = 1
        max_page = 1
        for btn in page_buttons:
            try:
                label = btn.get_attribute("aria-label") or ""
                if "Page" in label:
                    import re
                    match = re.search(r'Page (\d+)', label)
                    if match:
                        page_num = int(match.group(1))
                        max_page = max(max_page, page_num)
                        if "current" in label.lower():
                            current_page = page_num
            except:
                pass

        return max_page > current_page
