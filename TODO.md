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
- [x] Send profile data to Claude API for evaluation
- [x] Rate limiting (2-3 second delay between profile visits)

## Phase 3.5: Natural Language Query Parsing ✅ COMPLETE
- [x] `parse_query()` method uses Claude to extract structured criteria from natural language
- [x] Supports: company, team/product, role keywords, left_after, left_before, min/max_months_ago
- [x] Shows user what it understood (including team/product like "Uber Eats")
- [x] Generates optimized LinkedIn search query
- [x] Evaluates profiles against user's custom criteria
- [x] Auto-applies LinkedIn's "Past company" filter based on extracted company name

## Phase 4: Web UI & Export ✅ COMPLETE
- [x] Flask web interface (`app.py`)
- [x] Clean HTML/CSS UI (`templates/index.html`)
- [x] Windows launcher script (`launch.bat`)
- [x] Export to Excel (.xlsx) with download button
- [x] Status indicators for API key, browser, LinkedIn login
- [x] Success/error feedback messages

## Phase 5: Scale Testing & Final Features ← WAITING
- [ ] Test with LinkedIn Premium (currently limited to ~3 results without Premium)
- [ ] Test at scale with hundreds of profiles
- [ ] Performance optimization if needed
- [ ] Auto-messaging feature (potential future request from Dorsey)
- [ ] Package for easy distribution to Dorsey

---

## Current Status (as of 2026-01-28)

### What works:
- Run `python app.py` or double-click `launch.bat` to start
- Web UI opens at http://localhost:5000
- Set API key and launch browser from the UI
- Enter natural language queries like:
  - "Uber Eats engineers who left between 2023-2025"
  - "Former Google Maps engineers"
  - "Meta engineers who left in the last 6 months"
- Claude parses query → extracts company, team/product, role, time constraints
- Shows parsed criteria with team/product info (e.g., "Uber Eats")
- Searches LinkedIn with optimized query + Past Company filter
- Visits each profile, extracts full work history
- Claude evaluates each profile against criteria
- Download results as Excel file

### Waiting on:
1. **LinkedIn Premium** - Currently testing with ~3 results per search (free account limit)
2. **Scale testing** - Need to verify it works with hundreds of profiles
3. **Final specs from Dorsey** - May want additional features like auto-messaging

### To resume development:
1. Get LinkedIn Premium access for full search results
2. Test with larger result sets (50-100+ profiles)
3. Wait for Dorsey's feedback on additional feature requests
4. Then package for distribution

### Known limitations:
- LinkedIn free accounts only see ~3 search results
- Rate limiting (2-3 sec delay) means 100 profiles takes ~5 minutes to analyze
- Must keep terminal window open while app is running
