"""
Brain - LinkedIn Profile Search Tool
"""

from browser import LinkedInBrowser
from scraper import LinkedInScraper


def main():
    print("Brain - LinkedIn Profile Search Tool")
    print("=" * 40)

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

        # Phase 2: Search and scrape
        scraper = LinkedInScraper(browser)

        print("\n" + "=" * 40)
        print("Enter a search query (e.g., 'Uber Eats engineers')")
        print("Or press Enter to exit.")
        print("=" * 40)

        while True:
            query = input("\nSearch: ").strip()
            if not query:
                print("Goodbye!")
                break

            max_pages = input("How many pages to scrape? [1]: ").strip()
            max_pages = int(max_pages) if max_pages.isdigit() else 1

            print(f"\nSearching for: {query}")
            results = scraper.search(query, max_pages=max_pages)

            if results:
                print(f"\nFound {len(results)} profiles:")
                print("-" * 40)
                for i, r in enumerate(results, 1):
                    print(f"{i}. {r.name}")
                    print(f"   {r.url}")
                    if r.headline:
                        print(f"   {r.headline[:60]}...")
                    print()
            else:
                print("No results found.")


if __name__ == "__main__":
    main()
