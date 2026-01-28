"""
Brain - LinkedIn Profile Search Tool

Natural language search for LinkedIn profiles with customizable criteria.
"""

import os
from browser import LinkedInBrowser
from scraper import LinkedInScraper
from evaluator import ProfileEvaluator, SearchCriteria, ProfileAnalysis


def display_criteria(criteria: SearchCriteria) -> str:
    """Format criteria for display to user."""
    parts = [f"Company: {criteria.company}"]

    if criteria.role_keywords:
        parts.append(f"Role keywords: {', '.join(criteria.role_keywords)}")

    if criteria.still_employed_ok:
        parts.append("Including: Current employees")
    else:
        parts.append("Including: Former employees only")

    if criteria.left_after:
        parts.append(f"Left after: {criteria.left_after}")

    if criteria.left_before:
        parts.append(f"Left before: {criteria.left_before}")

    if criteria.min_months_ago:
        parts.append(f"Left more than: {criteria.min_months_ago} months ago")

    if criteria.max_months_ago:
        parts.append(f"Left within: last {criteria.max_months_ago} months")

    parts.append(f"LinkedIn search: \"{criteria.linkedin_search_query}\"")

    return "\n  ".join(parts)


def analyze_profiles(
    scraper: LinkedInScraper,
    evaluator: ProfileEvaluator,
    profiles: list,
    criteria: SearchCriteria
) -> list[ProfileAnalysis]:
    """
    Analyze each profile: extract work history and evaluate against criteria.

    Args:
        scraper: LinkedInScraper instance
        evaluator: ProfileEvaluator instance
        profiles: List of ProfileResult objects
        criteria: Parsed search criteria

    Returns:
        List of ProfileAnalysis objects
    """
    analyses = []
    total = len(profiles)

    for i, profile in enumerate(profiles, 1):
        print(f"\n[{i}/{total}] Analyzing: {profile.name}")
        print(f"    URL: {profile.url}")

        # Extract work experience from profile
        print("    Extracting work history...")
        work_history = scraper.get_profile_experience(profile.url)

        if work_history:
            print(f"    Found {len(work_history)} experience entries:")
            for exp in work_history[:3]:  # Show first 3
                print(f"      - {exp.title} at {exp.company}")
            if len(work_history) > 3:
                print(f"      ... and {len(work_history) - 3} more")
        else:
            print("    No work history found")

        # Evaluate against criteria
        print("    Evaluating against criteria...")
        result = evaluator.evaluate(criteria, work_history, profile.name)

        analysis = ProfileAnalysis(
            name=profile.name,
            url=profile.url,
            work_history=work_history,
            matches_criteria=result.matches_criteria,
            reasoning=result.reasoning,
            target_company=result.target_company,
            left_date=result.left_date,
            confidence=result.confidence
        )
        analyses.append(analysis)

        # Show result
        status = "MATCH" if result.matches_criteria else "NO MATCH"
        print(f"    Result: {status} ({result.confidence} confidence)")
        print(f"    Reason: {result.reasoning}")

    return analyses


def display_results(analyses: list[ProfileAnalysis]):
    """Display analysis results summary."""
    matches = [a for a in analyses if a.matches_criteria]
    non_matches = [a for a in analyses if not a.matches_criteria]

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"Total profiles analyzed: {len(analyses)}")
    print(f"Matches found: {len(matches)}")
    print(f"Non-matches: {len(non_matches)}")

    if matches:
        print("\n" + "-" * 40)
        print("MATCHING PROFILES:")
        print("-" * 40)
        for i, m in enumerate(matches, 1):
            print(f"\n{i}. {m.name}")
            print(f"   URL: {m.url}")
            if m.target_company:
                print(f"   Company: {m.target_company}")
            if m.left_date:
                print(f"   Left: {m.left_date}")
            print(f"   Confidence: {m.confidence}")
            print(f"   Reasoning: {m.reasoning}")

    return matches


def main():
    print("Brain - LinkedIn Profile Search Tool")
    print("=" * 40)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nWARNING: ANTHROPIC_API_KEY not set.")
        print("Profile analysis will not work without it.")
        print("Set it with: $env:ANTHROPIC_API_KEY=\"your_key_here\"")

    print("\nStarting browser with persistent Chrome session...")

    with LinkedInBrowser(headless=False) as browser:
        print("Checking LinkedIn login status...")

        if not browser.goto_linkedin():
            print("NOT LOGGED IN - Please log into LinkedIn in the browser window now.")
            input("\nAfter logging in, press Enter to verify and save session...")
            if not browser.goto_linkedin():
                print("ERROR: Still not logged in. Exiting.")
                return

        print("SUCCESS: Logged into LinkedIn!")

        # Initialize components
        scraper = LinkedInScraper(browser)

        # Initialize evaluator if API key is available
        evaluator = None
        try:
            evaluator = ProfileEvaluator()
            print("Claude API evaluator ready.")
        except ValueError as e:
            print(f"Note: {e}")
            print("Profiles will be scraped but not evaluated.")

        print("\n" + "=" * 40)
        print("Enter a natural language search query.")
        print("Examples:")
        print("  - Uber Eats engineers who left between 2023-2025")
        print("  - Former Google engineers")
        print("  - Meta engineers who left in the last 6 months")
        print("\nOr press Enter to exit.")
        print("=" * 40)

        while True:
            query = input("\nSearch: ").strip()
            if not query:
                print("Goodbye!")
                break

            if not evaluator:
                print("Error: Evaluator not available. Set ANTHROPIC_API_KEY.")
                continue

            # Parse the natural language query
            print("\nParsing your query...")
            criteria = evaluator.parse_query(query)

            # Show what we understood and confirm
            print("\nI understood your search as:")
            print(f"  {display_criteria(criteria)}")

            confirm = input("\nIs this correct? [Y/n]: ").strip().lower()
            if confirm == 'n':
                print("Please try rephrasing your query.")
                continue

            # Ask how many pages to scrape
            max_pages = input("How many pages to scrape? [1]: ").strip()
            max_pages = int(max_pages) if max_pages.isdigit() else 1

            # Search LinkedIn using the optimized search query + Past Company filter
            print(f"\nSearching LinkedIn for: {criteria.linkedin_search_query}")
            print(f"With 'Past company' filter: {criteria.company}")
            results = scraper.search(
                criteria.linkedin_search_query,
                max_pages=max_pages,
                past_company=criteria.company
            )

            if results:
                print(f"\nFound {len(results)} profiles:")
                print("-" * 40)
                for i, r in enumerate(results, 1):
                    print(f"{i}. {r.name}")
                    print(f"   {r.url}")
                    if r.headline:
                        print(f"   {r.headline[:60]}...")
                    print()

                # Ask if user wants to analyze profiles
                analyze = input("\nAnalyze these profiles? [Y/n]: ").strip().lower()
                if analyze != 'n':
                    # Ask how many to analyze
                    limit = input(f"How many profiles to analyze? [all={len(results)}]: ").strip()
                    if limit.isdigit():
                        limit = int(limit)
                        results = results[:limit]

                    print(f"\nAnalyzing {len(results)} profiles...")
                    print("(2-3 second delay between profiles to avoid rate limiting)")

                    analyses = analyze_profiles(scraper, evaluator, results, criteria)
                    matches = display_results(analyses)

                    if matches:
                        print(f"\n{len(matches)} candidates match your criteria!")
            else:
                print("No results found.")


if __name__ == "__main__":
    main()
