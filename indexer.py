#!/usr/bin/env python3
"""
Moltbook indexer - builds searchable SQLite database from scraped data.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("moltbook.db")
DATA_DIR = Path("data")

def init_db(conn):
    """Initialize database schema with FTS5 for full-text search."""
    conn.executescript("""
        -- Agents table
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            karma INTEGER DEFAULT 0,
            follower_count INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT
        );
        
        -- Posts table
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            title TEXT,
            content TEXT,
            author_id TEXT,
            submolt TEXT,
            upvotes INTEGER DEFAULT 0,
            downvotes INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            created_at TEXT,
            indexed_at TEXT,
            FOREIGN KEY (author_id) REFERENCES agents(id)
        );
        
        -- Full-text search index for posts
        CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
            title,
            content,
            author_name,
            content='posts',
            content_rowid='rowid'
        );
        
        -- Agent expertise (extracted from intros and post topics)
        CREATE TABLE IF NOT EXISTS agent_expertise (
            agent_id TEXT,
            topic TEXT,
            confidence REAL DEFAULT 1.0,
            source TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents(id),
            PRIMARY KEY (agent_id, topic)
        );
        
        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
            INSERT INTO posts_fts(rowid, title, content, author_name)
            SELECT NEW.rowid, NEW.title, NEW.content, 
                   (SELECT name FROM agents WHERE id = NEW.author_id);
        END;
    """)
    conn.commit()

def index_posts(conn, posts):
    """Index posts into the database."""
    now = datetime.utcnow().isoformat()
    
    for post in posts:
        author = post.get("author", {})
        
        # Upsert agent
        conn.execute("""
            INSERT INTO agents (id, name, karma, follower_count, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                karma = excluded.karma,
                follower_count = excluded.follower_count,
                last_seen = excluded.last_seen
        """, (
            author.get("id"),
            author.get("name"),
            author.get("karma", 0),
            author.get("follower_count", 0),
            now,
            now
        ))
        
        # Upsert post
        submolt = post.get("submolt", {})
        conn.execute("""
            INSERT INTO posts (id, title, content, author_id, submolt, upvotes, downvotes, comment_count, created_at, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                upvotes = excluded.upvotes,
                downvotes = excluded.downvotes,
                comment_count = excluded.comment_count,
                indexed_at = excluded.indexed_at
        """, (
            post.get("id"),
            post.get("title"),
            post.get("content"),
            author.get("id"),
            submolt.get("name"),
            post.get("upvotes", 0),
            post.get("downvotes", 0),
            post.get("comment_count", 0),
            post.get("created_at"),
            now
        ))
    
    conn.commit()
    print(f"Indexed {len(posts)} posts")

def search_posts(conn, query, limit=20):
    """Search posts using full-text search."""
    cursor = conn.execute("""
        SELECT p.id, p.title, p.content, a.name as author, p.upvotes, p.submolt
        FROM posts_fts fts
        JOIN posts p ON fts.rowid = p.rowid
        JOIN agents a ON p.author_id = a.id
        WHERE posts_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (query, limit))
    return cursor.fetchall()

def search_agents(conn, query, limit=20):
    """Search for agents by name or expertise."""
    cursor = conn.execute("""
        SELECT DISTINCT a.id, a.name, a.karma, a.follower_count
        FROM agents a
        LEFT JOIN posts p ON a.id = p.author_id
        LEFT JOIN posts_fts fts ON fts.rowid = p.rowid
        WHERE a.name LIKE ? OR posts_fts MATCH ?
        ORDER BY a.karma DESC
        LIMIT ?
    """, (f"%{query}%", query, limit))
    return cursor.fetchall()

def get_stats(conn):
    """Get index statistics."""
    agents = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    return {"agents": agents, "posts": posts}

if __name__ == "__main__":
    import sys
    
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    
    if len(sys.argv) < 2:
        print("Usage: python indexer.py [index|search|stats] [args...]")
        print(f"Current stats: {get_stats(conn)}")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "index":
        # Index all JSON files in data/
        for filepath in DATA_DIR.glob("*.json"):
            print(f"Indexing {filepath}...")
            with open(filepath) as f:
                data = json.load(f)
                posts = data if isinstance(data, list) else data.get("posts", [])
                index_posts(conn, posts)
    
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: python indexer.py search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        print(f"\nSearching for: {query}\n")
        
        print("=== Posts ===")
        for row in search_posts(conn, query):
            print(f"- [{row[3]}] {row[1] or '(no title)'} ({row[4]} upvotes)")
        
        print("\n=== Agents ===")
        for row in search_agents(conn, query):
            print(f"- {row[1]} (karma: {row[2]}, followers: {row[3]})")
    
    elif cmd == "stats":
        print(get_stats(conn))
    
    conn.close()
