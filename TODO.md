# Brain - Development Plan

## Phase 1: Browser Foundation ✅ COMPLETE
- [x] Set up Playwright with persistent Chrome context
- [x] Test that existing LinkedIn login session is preserved
- [x] Implement basic navigation to LinkedIn search

## Phase 2: Search & Scraping ✅ COMPLETE
- [x] Parse natural language query to extract company, role, date range
- [x] Execute LinkedIn search via search bar
- [x] Scrape search results page for profile URLs
- [x] Handle pagination (scroll/click for more results)
- [x] Filter out "mutual connection" mentions (both singular and plural)
- [x] Skip anonymous "LinkedIn Member" profiles

## Phase 3: Profile Analysis ✅ COMPLETE
- [x] Navigate to each profile URL
- [x] Extract profile text (work history, dates)
- [x] Send profile data to Claude API for Goldilocks evaluation
- [x] Criteria: Left >5 months ago, worked there in last 2.5 years
- [x] Rate limiting (2-3 second delay between profile visits)

## Phase 4: Output & Polish ← NEXT
- [ ] Collect matching profiles with metadata
- [ ] Export to Excel (.xlsx) using pandas
- [ ] Add CLI interface for query input
- [ ] Error handling and rate limiting

---

## Current Status (as of 2026-01-28)

**What works:**
- Run `python main.py` to start the tool
- Browser launches with persistent Chrome session (reuses your LinkedIn login)
- Enter a search query like "uber eats engineers"
- Specify number of pages to scrape
- Tool returns list of profile names and URLs
- Tool visits each profile and extracts work history
- Claude API evaluates each profile against Goldilocks criteria
- Displays matching profiles with reasoning

**What's next:**
- Phase 4: Export matching profiles to Excel, add polish
