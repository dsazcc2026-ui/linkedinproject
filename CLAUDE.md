# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Brain** - A LinkedIn profile search tool for Dorsey Asset Management. Takes natural language queries (e.g., "Find Uber Eats engineers who left between 2023-2025") and outputs Excel sheets of matching LinkedIn URLs.

## Architecture

- **Playwright** with persistent browser context (reuses analyst's existing Chrome login)
- **Claude API** for "Goldilocks" criteria evaluation (left >5 months ago, worked there in last 2.5 years)
- **pandas** for Excel output generation

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
