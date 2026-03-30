#!/bin/bash
set -e

# Initialize database
python -c "
import sqlite3, os
os.makedirs('/home/farm_agent/.farm_agent', exist_ok=True)
conn = sqlite3.connect('/home/farm_agent/.farm_agent/memory.db')
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS analyzed_repos (repo TEXT PRIMARY KEY, pr_count INTEGER DEFAULT 0, last_analyzed TEXT, status TEXT DEFAULT \"pending\")')
c.execute('CREATE TABLE IF NOT EXISTS friendly_repos (repo TEXT PRIMARY KEY, added_at TEXT DEFAULT CURRENT_TIMESTAMP, last_synced TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS submitted_prs (repo TEXT, pr_number INTEGER, pr_url TEXT, title TEXT, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, type TEXT, PRIMARY KEY (repo, pr_number))')
c.execute('CREATE TABLE IF NOT EXISTS task_schedule (task_key TEXT PRIMARY KEY, scheduled_at TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)')
for url in ['https://github.com/hieuit095/spring-petclinic-lite']:
    c.execute('INSERT OR IGNORE INTO friendly_repos (repo) VALUES (?)', (url,))
conn.commit()
print('DB init done. Friendly repos:', len(c.execute('SELECT repo FROM friendly_repos').fetchall()), flush=True)
conn.close()
"

echo "Starting scheduler..."
exec python -m farm_agent.cli.main schedule
