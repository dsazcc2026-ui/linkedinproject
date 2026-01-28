"""
Claude API evaluator for Goldilocks criteria.

Evaluates whether a candidate matches the criteria:
- Left target company >5 months ago (not too recent)
- Worked there within last 2.5 years (not too old)
"""

import os
from dataclasses import dataclass
from datetime import datetime
import anthropic
from scraper import WorkExperience


@dataclass
class EvaluationResult:
    """Result of Goldilocks criteria evaluation."""
    matches_criteria: bool
    reasoning: str
    target_company: str | None = None
    left_date: str | None = None
    confidence: str = "medium"  # low, medium, high


class GoldilocksEvaluator:
    """Evaluates candidates using Claude API against Goldilocks criteria."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def evaluate(
        self,
        search_query: str,
        work_history: list[WorkExperience],
        profile_name: str = "Unknown"
    ) -> EvaluationResult:
        """
        Evaluate a candidate's work history against Goldilocks criteria.

        Args:
            search_query: The original search query (to extract target company)
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

        prompt = f"""Evaluate this candidate against the "Goldilocks" criteria for a recruiting search.

SEARCH QUERY: "{search_query}"

CANDIDATE WORK HISTORY:
{work_history_text}

TODAY'S DATE: {today}

GOLDILOCKS CRITERIA:
1. Identify the TARGET COMPANY from the search query (e.g., "Uber Eats engineers" → target is "Uber Eats" or "Uber")
2. Did this person work at the target company? If not, they do NOT match.
3. If yes, when did they leave?
   - They must have LEFT MORE THAN 5 MONTHS AGO (not too recent - they need time to settle)
   - They must have WORKED THERE WITHIN THE LAST 2.5 YEARS (30 months) (not too old - experience should be recent)
   - If they show "Present" for the target company, they still work there and do NOT match

IMPORTANT: Calculate months carefully. For example:
- Aug 2024 to Jan 2026 = 17 months (Aug→Dec 2024 = 4 months, then all of 2025 = 12 months, then Jan 2026 = 1 month)
- Dec 2023 to Jan 2026 = 25 months

Respond in this exact format:
TARGET_COMPANY: [company name extracted from query]
WORKED_THERE: [Yes/No]
LEFT_DATE: [Month Year, or "Still there", or "Unknown"]
MONTHS_SINCE_LEFT: [show your calculation, e.g., "Aug 2024 to Jan 2026 = 17 months"]
MATCHES_CRITERIA: [Yes/No]
CONFIDENCE: [high/medium/low]
REASONING: [1-2 sentence explanation]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            return self._parse_response(response_text)

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

    def _parse_response(self, response_text: str) -> EvaluationResult:
        """Parse Claude's response into an EvaluationResult."""
        lines = response_text.strip().split('\n')
        result = {
            'target_company': None,
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
