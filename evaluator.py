"""
Claude API evaluator for natural language search criteria.

Parses natural language queries and evaluates candidates against extracted criteria.
"""

import os
import json
from dataclasses import dataclass
from datetime import datetime
import anthropic
from scraper import WorkExperience


@dataclass
class SearchCriteria:
    """Structured search criteria extracted from natural language query."""
    company: str
    team_or_product: str | None = None  # Specific team/division/product (e.g., "Uber Eats", "Google Maps")
    role_keywords: list[str] | None = None
    left_after: str | None = None      # "January 2023" or None
    left_before: str | None = None     # "December 2025" or None
    min_months_ago: int | None = None  # Must have left at least X months ago
    max_months_ago: int | None = None  # Must have left within last X months
    still_employed_ok: bool = False    # If True, current employees match
    original_query: str = ""
    linkedin_search_query: str = ""    # Optimized query for LinkedIn search


@dataclass
class EvaluationResult:
    """Result of candidate evaluation."""
    matches_criteria: bool
    reasoning: str
    target_company: str | None = None
    left_date: str | None = None
    confidence: str = "medium"  # low, medium, high


@dataclass
class ProfileAnalysis:
    """Complete analysis of a profile including work history and evaluation."""
    name: str
    url: str
    work_history: list[WorkExperience]
    matches_criteria: bool
    reasoning: str
    target_company: str | None = None
    left_date: str | None = None
    confidence: str = "medium"


class ProfileEvaluator:
    """Parses queries and evaluates candidates using Claude API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def parse_query(self, query: str) -> SearchCriteria:
        """
        Parse a natural language query into structured search criteria.

        Args:
            query: Natural language query like "Uber Eats engineers who left between 2023-2025"

        Returns:
            SearchCriteria with extracted parameters
        """
        today = datetime.now().strftime("%B %d, %Y")

        prompt = f"""Parse this recruiting search query into structured criteria.

QUERY: "{query}"

TODAY'S DATE: {today}

Extract the following information:
1. COMPANY: The parent company (e.g., "Uber", "Google", "Meta")
2. TEAM_OR_PRODUCT: Specific team, division, or product if mentioned (e.g., "Uber Eats", "Google Maps", "Instagram"), or null if not specified
3. ROLE_KEYWORDS: Any role/position keywords (e.g., ["engineer", "software"], or null if not specified)
4. LEFT_AFTER: Earliest date they could have left (e.g., "January 2023", or null if not specified)
5. LEFT_BEFORE: Latest date they could have left (e.g., "December 2025", or null if not specified)
6. MIN_MONTHS_AGO: If query says "left more than X months ago", put X here (or null)
7. MAX_MONTHS_AGO: If query says "left within last X months", put X here (or null)
8. STILL_EMPLOYED_OK: true if current employees should match, false if only former employees
9. LINKEDIN_SEARCH: Best search query to use on LinkedIn to find these people (keep it simple, 2-4 words)

Examples:
- "Uber Eats engineers who left between 2023-2025" → company: "Uber", team_or_product: "Uber Eats", left_after: "January 2023", left_before: "December 2025"
- "former Google Maps engineers" → company: "Google", team_or_product: "Google Maps", still_employed_ok: false
- "Meta engineers who left in the last 6 months" → company: "Meta", team_or_product: null, max_months_ago: 6
- "people who left Stripe more than 3 months ago" → company: "Stripe", team_or_product: null, min_months_ago: 3

Respond in this exact JSON format (no markdown, just raw JSON):
{{
  "company": "...",
  "team_or_product": "..." or null,
  "role_keywords": ["...", "..."] or null,
  "left_after": "Month Year" or null,
  "left_before": "Month Year" or null,
  "min_months_ago": number or null,
  "max_months_ago": number or null,
  "still_employed_ok": true or false,
  "linkedin_search": "..."
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON response
            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()

            data = json.loads(response_text)

            return SearchCriteria(
                company=data.get("company", "Unknown"),
                team_or_product=data.get("team_or_product"),
                role_keywords=data.get("role_keywords"),
                left_after=data.get("left_after"),
                left_before=data.get("left_before"),
                min_months_ago=data.get("min_months_ago"),
                max_months_ago=data.get("max_months_ago"),
                still_employed_ok=data.get("still_employed_ok", False),
                original_query=query,
                linkedin_search_query=data.get("linkedin_search", query)
            )

        except Exception as e:
            # Fallback: use query as-is
            print(f"    Warning: Could not parse query: {e}")
            return SearchCriteria(
                company=query,
                original_query=query,
                linkedin_search_query=query
            )

    def evaluate(
        self,
        criteria: SearchCriteria,
        work_history: list[WorkExperience],
        profile_name: str = "Unknown"
    ) -> EvaluationResult:
        """
        Evaluate a candidate's work history against the search criteria.

        Args:
            criteria: Parsed search criteria
            work_history: List of work experiences from the profile
            profile_name: Name of the candidate for context

        Returns:
            EvaluationResult with match status and reasoning
        """
        if not work_history:
            return EvaluationResult(
                matches_criteria=False,
                reasoning="No work history available to evaluate.",
                confidence="high"
            )

        # Format work history for the prompt
        work_history_text = self._format_work_history(work_history)
        today = datetime.now().strftime("%B %d, %Y")

        # Build criteria description
        criteria_parts = [f"1. Must have worked at {criteria.company}"]

        if criteria.role_keywords:
            criteria_parts.append(f"2. Role should match keywords: {', '.join(criteria.role_keywords)}")

        if criteria.still_employed_ok:
            criteria_parts.append("3. Current employees ARE allowed to match")
        else:
            criteria_parts.append("3. Must have LEFT the company (current employees do NOT match)")

        if criteria.left_after:
            criteria_parts.append(f"4. Must have left AFTER {criteria.left_after}")

        if criteria.left_before:
            criteria_parts.append(f"5. Must have left BEFORE {criteria.left_before}")

        if criteria.min_months_ago:
            criteria_parts.append(f"6. Must have left MORE THAN {criteria.min_months_ago} months ago")

        if criteria.max_months_ago:
            criteria_parts.append(f"7. Must have left WITHIN THE LAST {criteria.max_months_ago} months")

        criteria_text = "\n".join(criteria_parts)

        prompt = f"""Evaluate this candidate against the search criteria.

ORIGINAL QUERY: "{criteria.original_query}"

CANDIDATE WORK HISTORY:
{work_history_text}

TODAY'S DATE: {today}

CRITERIA TO CHECK:
{criteria_text}

IMPORTANT: Calculate dates carefully. For example:
- Aug 2024 to Jan 2026 = 17 months
- Dec 2023 to Jan 2026 = 25 months
- If someone shows "Present" for a company, they still work there.

Respond in this exact format:
TARGET_COMPANY: [the company from criteria]
WORKED_THERE: [Yes/No]
LEFT_DATE: [Month Year, or "Still there", or "Unknown"]
MATCHES_CRITERIA: [Yes/No]
CONFIDENCE: [high/medium/low]
REASONING: [1-2 sentence explanation of why they match or don't match]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            return self._parse_response(response_text, criteria.company)

        except Exception as e:
            return EvaluationResult(
                matches_criteria=False,
                reasoning=f"API error: {str(e)}",
                confidence="low"
            )

    def _format_work_history(self, work_history: list[WorkExperience]) -> str:
        """Format work history for the prompt."""
        lines = []
        for i, exp in enumerate(work_history, 1):
            date_str = ""
            if exp.start_date or exp.end_date:
                start = exp.start_date or "?"
                end = exp.end_date or "?"
                date_str = f" ({start} - {end})"
            elif exp.duration:
                date_str = f" ({exp.duration})"

            lines.append(f"{i}. {exp.title} at {exp.company}{date_str}")

        return "\n".join(lines) if lines else "No work history found"

    def _parse_response(self, response_text: str, default_company: str) -> EvaluationResult:
        """Parse Claude's response into an EvaluationResult."""
        lines = response_text.strip().split('\n')
        result = {
            'target_company': default_company,
            'left_date': None,
            'matches': False,
            'confidence': 'medium',
            'reasoning': ''
        }

        for line in lines:
            line = line.strip()
            if line.startswith('TARGET_COMPANY:'):
                result['target_company'] = line.split(':', 1)[1].strip()
            elif line.startswith('LEFT_DATE:'):
                result['left_date'] = line.split(':', 1)[1].strip()
            elif line.startswith('MATCHES_CRITERIA:'):
                value = line.split(':', 1)[1].strip().lower()
                result['matches'] = value == 'yes'
            elif line.startswith('CONFIDENCE:'):
                result['confidence'] = line.split(':', 1)[1].strip().lower()
            elif line.startswith('REASONING:'):
                result['reasoning'] = line.split(':', 1)[1].strip()

        return EvaluationResult(
            matches_criteria=result['matches'],
            reasoning=result['reasoning'] or "No reasoning provided",
            target_company=result['target_company'],
            left_date=result['left_date'],
            confidence=result['confidence']
        )


# Keep old class name for backwards compatibility
GoldilocksEvaluator = ProfileEvaluator
