"""
One-time (idempotent) migration: adds a `skill_category` column to `people`,
which the Task 2 n8n automation will fill in via an LLM classification step.

Safe to re-run: checks if the column already exists before adding it.
Run this AFTER merge_pipeline.py has created consultbae.db.
"""
import sqlite3
import os

# This script lives in task2/, the DB lives in task1/ (built by merge_pipeline.py)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "task1", "consultbae.db")

def main():
    con = sqlite3.connect(DB_PATH)
    cols = [r[1] for r in con.execute("PRAGMA table_info(people)")]
    if "skill_category" not in cols:
        con.execute("ALTER TABLE people ADD COLUMN skill_category TEXT")
        con.commit()
        print("Added skill_category column to people table.")
    else:
        print("skill_category column already exists — nothing to do.")
    con.close()

if __name__ == "__main__":
    main()