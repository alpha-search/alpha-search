#!/usr/bin/env python3
"""Alpha Search - API Connection Test Script.

Validates the credentials saved in .env for:
1. Alpha Vantage
2. Tavily Search API
3. X (Twitter) API
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Ensure repo root is on sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Load env file
load_dotenv(os.path.join(_REPO_ROOT, ".env"))

def test_alpha_vantage():
    print("[Test] Validating Alpha Vantage API...")
    api_key = os.getenv("ALPHA_VANTAGE_KEY")
    if not api_key:
        print("  - FAILED: ALPHA_VANTAGE_KEY not found in environment.")
        return False
        
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=IBM&apikey={api_key}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if "Global Quote" in data and data["Global Quote"]:
            print("  - SUCCESS: Alpha Vantage connection verified. IBM Price:", data["Global Quote"]["05. price"])
            return True
        elif "Note" in data:
            print("  - SUCCESS (Rate Limited): Alpha Vantage key valid, but returned API call frequency note:", data["Note"])
            return True
        else:
            print("  - FAILED: Alpha Vantage key invalid or empty response:", data)
            return False
    except Exception as e:
        print(f"  - FAILED: Connection error: {e}")
        return False

def test_tavily():
    print("[Test] Validating Tavily Search API...")
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("  - FAILED: TAVILY_API_KEY not found in environment.")
        return False
        
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": "NVIDIA Blackwell GPU cooling architecture news",
        "search_depth": "basic"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if "results" in data and data["results"]:
            print(f"  - SUCCESS: Tavily Search verified. Found {len(data['results'])} search results.")
            return True
        else:
            print("  - FAILED: Tavily Search key invalid or empty results:", data)
            return False
    except Exception as e:
        print(f"  - FAILED: Connection error: {e}")
        return False

def test_x_api():
    print("[Test] Validating X (Twitter) API (OAuth 2.0 Bearer/App-only auth)...")
    consumer_key = os.getenv("X_CONSUMER_KEY")
    consumer_secret = os.getenv("X_CONSUMER_SECRET")
    
    if not consumer_key or not consumer_secret:
        print("  - FAILED: X credentials missing in environment.")
        return False
        
    # Get Bearer Token
    auth_url = "https://api.twitter.com/oauth2/token"
    try:
        res = requests.post(
            auth_url,
            auth=(consumer_key, consumer_secret),
            data={"grant_type": "client_credentials"},
            timeout=10
        )
        if res.status_code == 200:
            token_data = res.json()
            bearer_token = token_data.get("access_token")
            if bearer_token:
                print("  - SUCCESS: X Client Credentials Auth verified. Bearer Token generated successfully.")
                return True
        print(f"  - FAILED: X Auth failed (HTTP {res.status_code}): {res.text}")
        return False
    except Exception as e:
        print(f"  - FAILED: Connection error: {e}")
        return False

def main():
    print("=" * 80)
    print("  ALPHA SEARCH - CREDENTIALS & CONNECTIONS VALIDATOR")
    print("=" * 80)
    
    av_ok = test_alpha_vantage()
    tav_ok = test_tavily()
    x_ok = test_x_api()
    
    print("\n" + "=" * 80)
    print("  CONNECTION SUMMARY")
    print("=" * 80)
    print(f"Alpha Vantage API : {'SUCCESS' if av_ok else 'FAILED'}")
    print(f"Tavily Search API : {'SUCCESS' if tav_ok else 'FAILED'}")
    print(f"X (Twitter) API   : {'SUCCESS' if x_ok else 'FAILED'}")
    print("=" * 80)

if __name__ == "__main__":
    main()
