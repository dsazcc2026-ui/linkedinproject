# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Brain** - A LinkedIn profile search tool for Dorsey Asset Management. Takes natural language queries (e.g., "Find Uber Eats engineers who left between 2023-2025") and outputs Excel sheets of matching LinkedIn URLs.

## Architecture

- **Playwright** with persistent browser context (reuses analyst's existing Chrome login)
- **Claude API** for "Goldilocks" criteria evaluation (left >5 months ago, worked there in last 2.5 years)
- **pandas** for Excel output generation

## Key Files

- `main.py` - Entry point, CLI loop for search queries
- `browser.py` - LinkedInBrowser class, handles Playwright browser with persistent session
- `scraper.py` - LinkedInScraper class, executes searches and extracts profile URLs
- `TODO.md` - Development roadmap with current status

## Current Status

**Phases 1 & 2 are COMPLETE.** The tool can:
- Launch browser with persistent Chrome session (reuses existing LinkedIn login)
- Accept natural language search queries
- Execute LinkedIn people search
- Scrape profile names and URLs from search results
- Handle pagination across multiple pages
- Filter out mutual connection mentions and anonymous profiles

**Phase 3 is NEXT:** Navigate to each profile, extract work history, evaluate with Claude API.

## Development

Run the main application:
```bash
python main.py
```

Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

## Environment

Requires `ANTHROPIC_API_KEY` environment variable for Claude API access.
