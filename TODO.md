# Brain - Development Plan

## Phase 1: Browser Foundation
- [x] Set up Playwright with persistent Chrome context
- [x] Test that existing LinkedIn login session is preserved
- [x] Implement basic navigation to LinkedIn search

## Phase 2: Search & Scraping
- [x] Parse natural language query to extract company, role, date range
- [x] Execute LinkedIn search via search bar
- [x] Scrape search results page for profile URLs
- [x] Handle pagination (scroll/click for more results)

## Phase 3: Profile Analysis
- [ ] Navigate to each profile URL
- [ ] Extract profile text (work history, dates)
- [ ] Send profile data to Claude API for Goldilocks evaluation
- [ ] Criteria: Left >5 months ago, worked there in last 2.5 years

## Phase 4: Output & Polish
- [ ] Collect matching profiles with metadata
- [ ] Export to Excel (.xlsx) using pandas
- [ ] Add CLI interface for query input
- [ ] Error handling and rate limiting
