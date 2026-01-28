"""
Brain - LinkedIn Profile Search Tool
Flask Web Interface
"""

import os
import json
from datetime import datetime
from io import BytesIO

from flask import Flask, render_template, request, jsonify, send_file, session
import pandas as pd

from browser import LinkedInBrowser
from scraper import LinkedInScraper
from evaluator import ProfileEvaluator, SearchCriteria, ProfileAnalysis

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global state for browser (persists across requests)
browser_state = {
    'browser': None,
    'scraper': None,
    'evaluator': None,
    'logged_in': False,
    'criteria': None,
    'search_results': None,
    'analyses': None
}


def get_evaluator():
    """Get or create the evaluator."""
    if browser_state['evaluator'] is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            browser_state['evaluator'] = ProfileEvaluator(api_key)
    return browser_state['evaluator']


@app.route('/')
def index():
    """Main page."""
    api_key_set = bool(os.environ.get('ANTHROPIC_API_KEY'))
    return render_template('index.html',
                         logged_in=browser_state['logged_in'],
                         api_key_set=api_key_set,
                         criteria=browser_state['criteria'],
                         search_results=browser_state['search_results'],
                         analyses=browser_state['analyses'])


@app.route('/set_api_key', methods=['POST'])
def set_api_key():
    """Set the API key."""
    data = request.json
    api_key = data.get('api_key', '').strip()
    if api_key:
        os.environ['ANTHROPIC_API_KEY'] = api_key
        browser_state['evaluator'] = None  # Reset to pick up new key
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'No API key provided'})


@app.route('/launch_browser', methods=['POST'])
def launch_browser():
    """Launch the browser and check login status."""
    try:
        if browser_state['browser'] is None:
            browser_state['browser'] = LinkedInBrowser(headless=False)
            browser_state['browser'].start()
            browser_state['scraper'] = LinkedInScraper(browser_state['browser'])

        # Check login status
        browser_state['logged_in'] = browser_state['browser'].goto_linkedin()

        return jsonify({
            'success': True,
            'logged_in': browser_state['logged_in']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/check_login', methods=['POST'])
def check_login():
    """Check if logged into LinkedIn."""
    if browser_state['browser'] is None:
        return jsonify({'success': False, 'error': 'Browser not launched'})

    browser_state['logged_in'] = browser_state['browser'].goto_linkedin()
    return jsonify({'success': True, 'logged_in': browser_state['logged_in']})


@app.route('/parse_query', methods=['POST'])
def parse_query():
    """Parse a natural language query into structured criteria."""
    data = request.json
    query = data.get('query', '').strip()

    if not query:
        return jsonify({'success': False, 'error': 'No query provided'})

    evaluator = get_evaluator()
    if not evaluator:
        return jsonify({'success': False, 'error': 'API key not set'})

    try:
        criteria = evaluator.parse_query(query)
        browser_state['criteria'] = criteria
        browser_state['search_results'] = None
        browser_state['analyses'] = None

        return jsonify({
            'success': True,
            'criteria': {
                'company': criteria.company,
                'team_or_product': criteria.team_or_product,
                'role_keywords': criteria.role_keywords,
                'still_employed_ok': criteria.still_employed_ok,
                'left_after': criteria.left_after,
                'left_before': criteria.left_before,
                'min_months_ago': criteria.min_months_ago,
                'max_months_ago': criteria.max_months_ago,
                'linkedin_search_query': criteria.linkedin_search_query,
                'original_query': criteria.original_query
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/search', methods=['POST'])
def search():
    """Execute LinkedIn search."""
    data = request.json
    max_pages = data.get('max_pages', 1)

    if not browser_state['logged_in']:
        return jsonify({'success': False, 'error': 'Not logged into LinkedIn'})

    if not browser_state['criteria']:
        return jsonify({'success': False, 'error': 'No search criteria set'})

    try:
        criteria = browser_state['criteria']
        results = browser_state['scraper'].search(
            criteria.linkedin_search_query,
            max_pages=max_pages,
            past_company=criteria.company
        )

        browser_state['search_results'] = results
        browser_state['analyses'] = None

        return jsonify({
            'success': True,
            'results': [{'name': r.name, 'url': r.url, 'headline': r.headline} for r in results]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze profiles against criteria."""
    data = request.json
    num_profiles = data.get('num_profiles', len(browser_state['search_results'] or []))

    if not browser_state['search_results']:
        return jsonify({'success': False, 'error': 'No search results'})

    evaluator = get_evaluator()
    if not evaluator:
        return jsonify({'success': False, 'error': 'API key not set'})

    try:
        criteria = browser_state['criteria']
        profiles = browser_state['search_results'][:num_profiles]
        analyses = []

        for profile in profiles:
            work_history = browser_state['scraper'].get_profile_experience(profile.url)
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

        browser_state['analyses'] = analyses

        return jsonify({
            'success': True,
            'analyses': [{
                'name': a.name,
                'url': a.url,
                'matches': a.matches_criteria,
                'confidence': a.confidence,
                'target_company': a.target_company,
                'left_date': a.left_date,
                'reasoning': a.reasoning
            } for a in analyses]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/export')
def export():
    """Export results to Excel."""
    if not browser_state['analyses']:
        return jsonify({'success': False, 'error': 'No analysis results'})

    analyses = browser_state['analyses']
    criteria = browser_state['criteria']

    data = []
    for a in analyses:
        data.append({
            'Name': a.name,
            'LinkedIn URL': a.url,
            'Match': 'Yes' if a.matches_criteria else 'No',
            'Confidence': a.confidence,
            'Target Company': a.target_company or '',
            'Left Date': a.left_date or '',
            'Reasoning': a.reasoning
        })

    df = pd.DataFrame(data)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_slug = criteria.company.replace(' ', '_').lower() if criteria else 'results'
    filename = f"brain_results_{company_slug}_{timestamp}.xlsx"

    # Create Excel file in memory
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Results')
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


@app.route('/status')
def status():
    """Get current status."""
    return jsonify({
        'logged_in': browser_state['logged_in'],
        'api_key_set': bool(os.environ.get('ANTHROPIC_API_KEY')),
        'has_criteria': browser_state['criteria'] is not None,
        'has_results': browser_state['search_results'] is not None,
        'has_analyses': browser_state['analyses'] is not None,
        'num_results': len(browser_state['search_results']) if browser_state['search_results'] else 0,
        'num_analyses': len(browser_state['analyses']) if browser_state['analyses'] else 0
    })


if __name__ == '__main__':
    print("\n" + "="*50)
    print("Brain - LinkedIn Profile Search Tool")
    print("="*50)
    print("\nStarting web server...")
    print("Open http://localhost:5000 in your browser")
    print("\nPress Ctrl+C to stop\n")

    app.run(debug=False, port=5000, threaded=False)
