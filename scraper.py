#!/usr/bin/env python3
"""
Moltbook scraper - fetches agent profiles and posts for indexing.
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path

API_BASE = "https://www.moltbook.com/api/v1"
DATA_DIR = Path("data")

def get_headers():
    """Get auth headers. Set MOLTBOOK_API_KEY env var."""
    api_key = os.environ.get("MOLTBOOK_API_KEY")
    if not api_key:
        raise ValueError("Set MOLTBOOK_API_KEY environment variable")
    return {"Authorization": f"Bearer {api_key}"}

def fetch_posts(sort="hot", limit=100, offset=0):
    """Fetch posts from Moltbook."""
    resp = requests.get(
        f"{API_BASE}/posts",
        headers=get_headers(),
        params={"sort": sort, "limit": limit, "offset": offset}
    )
    resp.raise_for_status()
    return resp.json()

def fetch_submolt_posts(submolt_name, limit=100, offset=0):
    """Fetch posts from a specific submolt (e.g., 'introductions')."""
    resp = requests.get(
        f"{API_BASE}/submolts/{submolt_name}/posts",
        headers=get_headers(),
        params={"limit": limit, "offset": offset}
    )
    resp.raise_for_status()
    return resp.json()

def save_posts(posts, filename):
    """Save posts to JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    filepath = DATA_DIR / filename
    with open(filepath, "w") as f:
        json.dump(posts, f, indent=2)
    print(f"Saved {len(posts)} posts to {filepath}")

def scrape_all_posts(max_pages=10):
    """Scrape posts across multiple pages."""
    all_posts = []
    offset = 0
    limit = 100
    
    for page in range(max_pages):
        print(f"Fetching page {page + 1}...")
        data = fetch_posts(sort="new", limit=limit, offset=offset)
        posts = data.get("posts", [])
        
        if not posts:
            break
            
        all_posts.extend(posts)
        
        if not data.get("has_more"):
            break
            
        offset += limit
    
    return all_posts

def scrape_introductions():
    """Scrape m/introductions for agent profiles."""
    all_posts = []
    offset = 0
    limit = 100
    
    while True:
        print(f"Fetching introductions (offset {offset})...")
        try:
            data = fetch_submolt_posts("introductions", limit=limit, offset=offset)
            posts = data.get("posts", [])
            
            if not posts:
                break
                
            all_posts.extend(posts)
            
            if not data.get("has_more"):
                break
                
            offset += limit
        except Exception as e:
            print(f"Error fetching introductions: {e}")
            break
    
    return all_posts

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python scraper.py [posts|introductions|all]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if cmd == "posts":
        posts = scrape_all_posts()
        save_posts(posts, f"posts_{timestamp}.json")
    elif cmd == "introductions":
        posts = scrape_introductions()
        save_posts(posts, f"introductions_{timestamp}.json")
    elif cmd == "all":
        posts = scrape_all_posts()
        save_posts(posts, f"posts_{timestamp}.json")
        intros = scrape_introductions()
        save_posts(intros, f"introductions_{timestamp}.json")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
