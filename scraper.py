"""
LinkedIn search results scraper.
"""

import re
import time
import urllib.parse
from dataclasses import dataclass
from browser import LinkedInBrowser


@dataclass
class ProfileResult:
    """A LinkedIn profile from search results."""
    name: str
    url: str
    headline: str | None = None


@dataclass
class WorkExperience:
    """A work experience entry from a LinkedIn profile."""
    company: str
    title: str
    start_date: str | None = None  # "Jan 2020" format
    end_date: str | None = None    # "Present" or "Dec 2023"
    duration: str | None = None    # "2 yrs 3 mos"


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

    def search(self, query: str, max_pages: int = 1, past_company: str = None) -> list[ProfileResult]:
        """
        Execute a search and return profile results.

        Args:
            query: Natural language search query
            max_pages: Maximum number of result pages to scrape
            past_company: If provided, apply LinkedIn's "Past company" filter

        Returns:
            List of ProfileResult objects
        """
        parsed = parse_search_query(query)
        all_results = []

        # Navigate to first page
        url = build_search_url(parsed["keywords"], 1)
        self.page.goto(url, timeout=60000)
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_timeout(3000)

        # Apply past company filter if specified
        if past_company:
            print(f"  Applying 'Past company' filter: {past_company}")
            if not self._apply_past_company_filter(past_company):
                print("  Warning: Could not apply past company filter, continuing with keyword search")

        for page_num in range(1, max_pages + 1):
            print(f"  Scraping page {page_num}...")

            # For page 2+, click Next button to preserve filters
            if page_num > 1:
                if not self._goto_next_page():
                    print(f"  Could not navigate to page {page_num}, stopping.")
                    break
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

    def _goto_next_page(self) -> bool:
        """
        Click the Next button to go to the next page of results.
        This preserves any applied filters (unlike URL navigation).

        Returns:
            True if navigation succeeded, False otherwise
        """
        try:
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
                        next_button.click()
                        self.page.wait_for_timeout(2000)
                        return True

            return False
        except Exception as e:
            print(f"    Error navigating to next page: {e}")
            return False

    def _apply_past_company_filter(self, company: str) -> bool:
        """
        Apply LinkedIn's 'Past company' filter.

        Args:
            company: Company name to filter by

        Returns:
            True if filter was applied successfully, False otherwise
        """
        try:
            # Click "All filters" button
            all_filters_btn = self.page.query_selector('button:has-text("All filters")')
            if not all_filters_btn:
                # Try alternative selector
                all_filters_btn = self.page.query_selector('button[aria-label*="filter"]')
            if not all_filters_btn:
                print("    Could not find 'All filters' button")
                return False

            all_filters_btn.click()
            self.page.wait_for_timeout(2000)

            # Scroll down in the filter panel to reveal "Past company" section
            self.page.evaluate('''() => {
                document.querySelectorAll('div').forEach(el => {
                    if (el.scrollHeight > el.clientHeight && el.clientHeight > 200) {
                        el.scrollTop = el.scrollHeight / 2;
                    }
                });
            }''')
            self.page.wait_for_timeout(1000)

            past_company_input = None

            # Click the SECOND "Add a company" button (first is current, second is past)
            result = self.page.evaluate('''(company) => {
                // Find all buttons with "Add a company" text
                const buttons = Array.from(document.querySelectorAll('button'));
                const companyButtons = buttons.filter(btn => {
                    let text = (btn.innerText || '').trim().toLowerCase();
                    return text === 'add a company';
                });

                if (companyButtons.length < 2) {
                    return { success: false, error: 'not_enough_buttons', count: companyButtons.length };
                }

                // Get the second button (Past company)
                const pastCompanyBtn = companyButtons[1];

                // Click the button to reveal the input
                pastCompanyBtn.click();

                return { success: true, clicked: 'second' };
            }''' , company)

            if result.get('success'):
                self.page.wait_for_timeout(1500)

                # The input that appears has placeholder "Add a company"
                past_company_input = self.page.query_selector('input[placeholder="Add a company"]')
            else:
                print("    Could not find 'Add a company' buttons in filter panel")

            if not past_company_input:
                print("    Could not find 'Past company' input field")
                # Close the filter panel
                close_btn = self.page.query_selector('button[aria-label="Dismiss"], button[aria-label="Close"]')
                if close_btn:
                    close_btn.click()
                return False

            # Type the company name
            past_company_input.click()
            past_company_input.fill(company)
            self.page.wait_for_timeout(1500)  # Wait for autocomplete

            # Select first autocomplete suggestion
            # LinkedIn typically shows suggestions in a listbox or dropdown
            suggestion = self.page.query_selector('[role="listbox"] [role="option"], .basic-typeahead__selectable')
            if suggestion:
                suggestion.click()
                self.page.wait_for_timeout(500)
            else:
                # Try pressing Enter to confirm
                past_company_input.press("Enter")
                self.page.wait_for_timeout(500)

            # Click "Show results" button to apply filters
            show_results_btn = self.page.query_selector('button:has-text("Show results")')
            if not show_results_btn:
                show_results_btn = self.page.query_selector('button[aria-label*="Apply"], button:has-text("Apply")')

            if show_results_btn:
                show_results_btn.click()
                self.page.wait_for_timeout(3000)  # Wait for results to reload
                print(f"    Applied 'Past company' filter for: {company}")
                return True
            else:
                print("    Could not find 'Show results' button")
                return False

        except Exception as e:
            print(f"    Error applying past company filter: {e}")
            # Try to close any open modal
            try:
                close_btn = self.page.query_selector('button[aria-label="Dismiss"], button[aria-label="Close"]')
                if close_btn:
                    close_btn.click()
            except:
                pass
            return False

    def get_profile_experience(self, profile_url: str, delay: float = 2.5, debug: bool = True) -> list[WorkExperience]:
        """
        Visit a profile and extract work experience history.

        Args:
            profile_url: LinkedIn profile URL
            delay: Seconds to wait before visiting (rate limiting)
            debug: If True, save debug info to files

        Returns:
            List of WorkExperience objects
        """
        # Rate limiting delay
        if delay > 0:
            time.sleep(delay)

        # Navigate directly to the full experience details page
        # This shows ALL experiences, not just the preview
        experience_url = profile_url.rstrip('/') + '/details/experience/'
        self.page.goto(experience_url, timeout=60000)
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_timeout(3000)  # Wait for dynamic content

        experiences = []

        try:
            # Scroll down to load all experiences
            self.page.evaluate("window.scrollTo(0, 500)")
            self.page.wait_for_timeout(800)
            self.page.evaluate("window.scrollTo(0, 1000)")
            self.page.wait_for_timeout(800)
            self.page.evaluate("window.scrollTo(0, 2000)")
            self.page.wait_for_timeout(800)

            # Save debug screenshot
            if debug:
                self.page.screenshot(path="debug_profile.png")

            # Use JavaScript to extract all experience data directly
            experiences = self._extract_experience_via_js(debug=debug)

        except Exception as e:
            print(f"    Warning: Error extracting experience: {e}")

        return experiences

    def _extract_experience_via_js(self, debug: bool = False) -> list[WorkExperience]:
        """Extract experience using JavaScript to parse the page."""
        experiences = []

        try:
            # Extract experience data using JavaScript
            # Simpler approach: get the full text of each top-level experience item
            exp_data = self.page.evaluate(r'''() => {
                let results = [];

                // Get all top-level experience items
                let items = document.querySelectorAll('li.pvs-list__paged-list-item');

                for (let item of items) {
                    // Get the full inner text of this item
                    let fullText = item.innerText.trim();

                    // Skip if too short or too long
                    if (fullText.length < 20 || fullText.length > 3000) continue;

                    // Skip if it looks like a "Show more" button
                    if (fullText.toLowerCase().includes('show all') ||
                        fullText.toLowerCase().includes('see more')) continue;

                    // Also get structured spans for better parsing
                    let spans = item.querySelectorAll(':scope > div span[aria-hidden="true"]');
                    let topSpans = [];
                    spans.forEach(s => {
                        let t = s.innerText.trim();
                        if (t && t.length > 0 && t.length < 200) {
                            topSpans.push(t);
                        }
                    });

                    // Check if this has nested roles (multiple positions at same company)
                    let nestedUl = item.querySelector(':scope > div > div > ul');
                    let hasNested = nestedUl && nestedUl.querySelectorAll(':scope > li').length > 0;

                    results.push({
                        fullText: fullText,
                        topSpans: topSpans,
                        hasNested: hasNested
                    });
                }

                return results;
            }''')

            # Debug: save raw extraction data to file
            if debug and exp_data:
                import json
                with open("debug_raw_experience.json", "w", encoding="utf-8") as f:
                    json.dump(exp_data, f, indent=2, ensure_ascii=False)
                print(f"    Debug: Raw data saved to debug_raw_experience.json ({len(exp_data)} entries)")

            # Parse each extracted entry
            for item in exp_data:
                full_text = item.get('fullText', '')
                has_nested = item.get('hasNested', False)

                if has_nested:
                    # This item has multiple roles at one company - parse each
                    parsed = self._parse_nested_experience(full_text)
                    for exp in parsed:
                        if exp and exp.title != "Unknown":
                            is_dup = any(e.company == exp.company and e.title == exp.title for e in experiences)
                            if not is_dup:
                                experiences.append(exp)
                else:
                    # Single role - parse directly
                    exp = self._parse_single_experience(full_text)
                    if exp and exp.title != "Unknown":
                        is_dup = any(e.company == exp.company and e.title == exp.title for e in experiences)
                        if not is_dup:
                            experiences.append(exp)

        except Exception as e:
            print(f"    Debug: JS extraction error: {e}")

        return experiences

    def _parse_single_experience(self, full_text: str) -> WorkExperience | None:
        """Parse a single job entry from its full text."""
        if not full_text or len(full_text) < 10:
            return None

        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        if len(lines) < 2:
            return None

        # Skip UI elements
        if any(skip in full_text.lower() for skip in ['show all', 'see more', 'see less']):
            return None

        title = None
        company = None
        start_date = None
        end_date = None
        duration = None

        # Patterns
        date_range_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*[-–]\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present)'
        duration_pattern = r'(\d+\s*(?:yr|yrs|mo|mos)(?:\s*\d+\s*(?:yr|yrs|mo|mos))?)'

        for line in lines:
            # Check for date range
            range_match = re.search(date_range_pattern, line, re.IGNORECASE)
            if range_match and not start_date:
                start_date = range_match.group(1)
                end_date = range_match.group(2)
                # Also try to get duration from same line
                dur_match = re.search(r'·\s*' + duration_pattern, line)
                if dur_match:
                    duration = dur_match.group(1)
                continue

            # Check for standalone duration
            if re.match(r'^\d+\s*(yr|yrs|mo|mos)', line):
                duration = line.split('·')[0].strip()
                continue

            # Skip location lines
            if re.match(r'^(Remote|Hybrid|On-?site|United States|San Francisco|New York|London|Seattle|Chicago|Los Angeles|Austin|Bengaluru|India|California)', line, re.IGNORECASE):
                continue

            # Skip employment type standalone
            if re.match(r'^(Full-time|Part-time|Contract|Internship|Self-employed|Freelance)$', line, re.IGNORECASE):
                continue

            # Skip descriptions (usually longer lines or start with bullet points)
            if len(line) > 100 or line.startswith('•') or line.startswith('-'):
                continue

            # First valid line is usually title
            if not title and len(line) > 2 and len(line) < 80:
                title = line
            # Second is usually company
            elif not company and len(line) > 1 and len(line) < 80 and line != title:
                # Clean company name (remove "· Full-time" etc)
                company = re.split(r'\s*·\s*', line)[0].strip()

        if title or company:
            return WorkExperience(
                company=company or "Unknown",
                title=title or "Unknown",
                start_date=start_date,
                end_date=end_date,
                duration=duration
            )
        return None

    def _parse_nested_experience(self, full_text: str) -> list[WorkExperience]:
        """Parse multiple roles at the same company from full text."""
        results = []
        if not full_text:
            return results

        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        if len(lines) < 3:
            return results

        # First line is usually the company name
        # Second line might be total duration like "5 yrs 2 mos"
        company = None
        for line in lines[:3]:
            # Skip duration-only lines
            if re.match(r'^\d+\s*(yr|yrs|mo|mos)', line):
                continue
            # Skip "Full-time" etc
            if re.match(r'^(Full-time|Part-time|Contract)$', line, re.IGNORECASE):
                continue
            if not company and len(line) > 1 and len(line) < 100:
                company = line
                break

        if not company:
            return results

        # Now find each role - they usually have date patterns
        date_range_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*[-–]\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present)'

        current_title = None
        current_start = None
        current_end = None
        current_duration = None

        for i, line in enumerate(lines):
            # Check for date range - this usually marks a role
            range_match = re.search(date_range_pattern, line, re.IGNORECASE)
            if range_match:
                # Save previous role if we have one
                if current_title:
                    results.append(WorkExperience(
                        company=company,
                        title=current_title,
                        start_date=current_start,
                        end_date=current_end,
                        duration=current_duration
                    ))

                # Start new role - title should be the previous line
                current_start = range_match.group(1)
                current_end = range_match.group(2)

                # Get duration from same line if present
                dur_match = re.search(r'·\s*(\d+\s*(?:yr|yrs|mo|mos)(?:\s*\d+\s*(?:mo|mos))?)', line)
                current_duration = dur_match.group(1) if dur_match else None

                # Look for title in previous lines
                for j in range(i - 1, max(0, i - 3), -1):
                    prev_line = lines[j]
                    # Skip company name, durations, locations
                    if prev_line == company:
                        continue
                    if re.match(r'^\d+\s*(yr|yrs|mo|mos)', prev_line):
                        continue
                    if re.match(r'^(Full-time|Part-time|Remote|Hybrid|On-?site)', prev_line, re.IGNORECASE):
                        continue
                    if len(prev_line) > 2 and len(prev_line) < 80:
                        current_title = prev_line
                        break

        # Don't forget the last role
        if current_title:
            results.append(WorkExperience(
                company=company,
                title=current_title,
                start_date=current_start,
                end_date=current_end,
                duration=current_duration
            ))

        return results

    def _parse_structured_experience(self, texts: list[str], company_override: str = None) -> WorkExperience | None:
        """Parse experience from a list of text spans (more reliable than raw text)."""
        if not texts or len(texts) < 2:
            return None

        company = company_override  # Use override if provided (for nested roles)
        title = None
        start_date = None
        end_date = None
        duration = None

        # Patterns
        date_range_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*[-–]\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present)'
        duration_pattern = r'^\d+\s*(yr|yrs|mo|mos)'
        single_date_pattern = r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}$'

        # Skip patterns
        skip_patterns = ['see more', 'show all', 'skills', 'endorsement',
                        'recommendation', 'license', 'certification']

        for text in texts:
            text = text.strip()
            if not text or len(text) < 2:
                continue

            text_lower = text.lower()

            # Skip UI elements
            if any(p in text_lower for p in skip_patterns):
                return None

            # Check for date range (e.g., "Jan 2020 - Present")
            range_match = re.search(date_range_pattern, text, re.IGNORECASE)
            if range_match:
                start_date = range_match.group(1)
                end_date = range_match.group(2)
                continue

            # Check for duration (e.g., "2 yrs 3 mos")
            if re.match(duration_pattern, text, re.IGNORECASE):
                duration = text
                continue

            # Check for single date
            if re.match(single_date_pattern, text, re.IGNORECASE):
                if not start_date:
                    start_date = text
                continue

            # Skip location-like entries
            if re.match(r'^(Remote|Hybrid|On-?site|United States|San Francisco|New York|London|Seattle|Chicago|Los Angeles|Austin|·)', text, re.IGNORECASE):
                continue

            # Skip employment type
            if re.match(r'^(Full-time|Part-time|Contract|Internship|Self-employed|Freelance|Seasonal|Apprenticeship)$', text, re.IGNORECASE):
                continue

            # First real text is usually the title
            if not title and len(text) > 2 and len(text) < 100:
                title = text
            # Second is usually company (if we don't already have one from override)
            elif not company and len(text) > 1 and len(text) < 100:
                # Don't set company if it looks like it's the same as title
                if text != title:
                    company = text

        # Clean up: if company contains "· Full-time" etc, strip it
        if company:
            company = re.split(r'\s*·\s*', company)[0].strip()

        if title or company:
            return WorkExperience(
                company=company or "Unknown",
                title=title or "Unknown",
                start_date=start_date,
                end_date=end_date,
                duration=duration
            )

        return None

    def _parse_experience_text(self, text: str) -> WorkExperience | None:
        """Parse experience from a text block."""
        if not text or len(text) < 10:
            return None

        # Skip UI elements and non-job entries
        text_lower = text.lower()
        skip_patterns = ['see more', 'show all', 'show more', 'see all', 'skills',
                        'endorsement', 'recommendation', 'license', 'certification',
                        'education', 'course', 'volunteer', 'publication']
        if any(pattern in text_lower for pattern in skip_patterns):
            return None

        # Split by common delimiters
        lines = []
        for line in text.replace(' | ', '\n').split('\n'):
            line = line.strip()
            if line and len(line) > 1:
                lines.append(line)

        if not lines:
            return None

        company = None
        title = None
        start_date = None
        end_date = None
        duration = None

        # Patterns
        date_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}'
        duration_pattern = r'\d+\s*(yr|yrs|mo|mos)'
        date_range_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*[-–]\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present)'

        for line in lines:
            # Check for date range
            range_match = re.search(date_range_pattern, line, re.IGNORECASE)
            if range_match:
                start_date = range_match.group(1)
                end_date = range_match.group(2)
                continue

            # Check for duration
            if re.search(duration_pattern, line, re.IGNORECASE) and not title:
                duration = line
                continue

            # Check if line is just a date
            if re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}', line, re.IGNORECASE):
                if not start_date:
                    start_date = line
                continue

            # Skip location-like lines
            if re.match(r'^(Remote|United States|San Francisco|New York|London|·)', line, re.IGNORECASE):
                continue

            # Skip "Full-time", "Part-time", etc
            if re.match(r'^(Full-time|Part-time|Contract|Internship|Self-employed)$', line, re.IGNORECASE):
                continue

            # First substantial line is usually title
            if not title and len(line) > 2 and len(line) < 100:
                title = line
            # Second is usually company (but not if it's the same as title)
            elif not company and len(line) > 2 and len(line) < 100 and line != title:
                company = line

        # If company equals title, try to split by comma or clear company
        if company and title and company == title:
            # Try to extract company from title like "Title at Company" or "Title, Company"
            if ' at ' in title:
                parts = title.split(' at ', 1)
                title = parts[0].strip()
                company = parts[1].strip()
            elif ', ' in title:
                parts = title.split(', ', 1)
                title = parts[0].strip()
                company = parts[1].strip()
            else:
                company = None  # Clear duplicate

        # Only return if we have meaningful data
        if title or company:
            return WorkExperience(
                company=company or "Unknown",
                title=title or "Unknown",
                start_date=start_date,
                end_date=end_date,
                duration=duration
            )

        return None
