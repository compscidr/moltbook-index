#!/usr/bin/env python3
"""
Build a JSON search index for the static site.
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path("data")
OUTPUT = Path("docs/search-index.json")

# Patterns for secrets to redact
SECRET_PATTERNS = [
    (r'sk-proj-[a-zA-Z0-9]{40,}', '[REDACTED_API_KEY]'),  # OpenAI project keys
    (r'sk-[a-zA-Z0-9]{20,}', '[REDACTED_API_KEY]'),  # OpenAI keys
    (r'moltbook_sk_[a-zA-Z0-9_-]+', '[REDACTED_API_KEY]'),  # Moltbook keys
    (r'ghp_[a-zA-Z0-9]{36}', '[REDACTED_TOKEN]'),  # GitHub PATs
    (r'gho_[a-zA-Z0-9]{36}', '[REDACTED_TOKEN]'),  # GitHub OAuth
    (r'github_pat_[a-zA-Z0-9_]{22,}', '[REDACTED_TOKEN]'),  # GitHub fine-grained
    (r'xoxb-[a-zA-Z0-9-]+', '[REDACTED_TOKEN]'),  # Slack bot tokens
    (r'xoxp-[a-zA-Z0-9-]+', '[REDACTED_TOKEN]'),  # Slack user tokens
]

def sanitize(text):
    """Remove potential secrets from text."""
    if not text:
        return text
    for pattern, replacement in SECRET_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text

def build_index():
    """Build search index from scraped data."""
    all_posts = []
    agents = {}
    
    # Load all JSON files
    for filepath in DATA_DIR.glob("*.json"):
        print(f"Loading {filepath}...")
        with open(filepath) as f:
            data = json.load(f)
            posts = data if isinstance(data, list) else data.get("posts", [])
            all_posts.extend(posts)
    
    # Deduplicate by post ID
    seen = set()
    unique_posts = []
    for post in all_posts:
        if post.get("id") not in seen:
            seen.add(post.get("id"))
            unique_posts.append(post)
            
            # Track agents
            author = post.get("author", {})
            if author.get("id"):
                agents[author["id"]] = {
                    "id": author["id"],
                    "name": author.get("name"),
                    "karma": author.get("karma", 0),
                    "follower_count": author.get("follower_count", 0)
                }
    
    # Build simplified index for frontend (with sanitization)
    index_posts = []
    for post in unique_posts:
        author = post.get("author", {})
        submolt = post.get("submolt", {})
        index_posts.append({
            "id": post.get("id"),
            "title": sanitize(post.get("title")),
            "content": sanitize(post.get("content")),
            "author": author.get("name"),
            "author_id": author.get("id"),
            "submolt": submolt.get("name") if submolt else None,
            "upvotes": post.get("upvotes", 0),
            "comment_count": post.get("comment_count", 0),
            "created_at": post.get("created_at")
        })
    
    # Sort by upvotes
    index_posts.sort(key=lambda x: x["upvotes"], reverse=True)
    
    index = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "posts": index_posts,
        "agents": list(agents.values())
    }
    
    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(index, f)
    
    print(f"Built index: {len(index_posts)} posts, {len(agents)} agents")
    print(f"Output: {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    build_index()
