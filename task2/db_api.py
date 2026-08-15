"""

Run: python3 db_api.py
Listens on http://localhost:5000

Endpoints:
  GET  /health
  GET  /people/untagged
        -> [{ "person_id": 1, "canonical_name": "...", "skills": "n8n, sql, ..." }, ...]
       Combines skills from naukri_applications.skills and
       gig_worker_profiles.skill_tags (dedup'd), for anyone with
       skill_category still NULL.
  POST /people/<person_id>/tag
        body: {"category": "automation-heavy"}
       Writes the category into people.skill_category.
"""
import sqlite3
from flask import Flask, jsonify, request

import os
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "task1", "consultbae.db")
app = Flask(__name__)


def get_con():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/people/untagged")
def untagged():
    con = get_con()
    rows = con.execute("""
        SELECT p.person_id, p.canonical_name,
               COALESCE(n.skills, '') AS naukri_skills,
               COALESCE(g.skill_tags, '') AS gig_skills
        FROM people p
        LEFT JOIN naukri_applications n ON n.person_id = p.person_id
        LEFT JOIN gig_worker_profiles g ON g.person_id = p.person_id
        WHERE p.skill_category IS NULL
    """).fetchall()
    con.close()

    out = []
    for r in rows:
        combined = set()
        for src in (r["naukri_skills"], r["gig_skills"]):
            if src:
                combined.update(s.strip() for s in src.split(",") if s.strip())
        if not combined:
            continue  # nothing to classify on
        out.append({
            "person_id": r["person_id"],
            "canonical_name": r["canonical_name"],
            "skills": ", ".join(sorted(combined)),
        })
    return jsonify(out)


@app.route("/people/<int:person_id>/tag", methods=["POST"])
def tag_person(person_id):
    data = request.get_json(force=True) or {}
    category = (data.get("category") or "").strip()
    if not category:
        return jsonify({"error": "category is required"}), 400

    con = get_con()
    cur = con.execute(
        "UPDATE people SET skill_category = ? WHERE person_id = ?",
        (category, person_id),
    )
    con.commit()
    updated = cur.rowcount
    con.close()

    if updated == 0:
        return jsonify({"error": f"no person with id {person_id}"}), 404
    return jsonify({"person_id": person_id, "skill_category": category})


if __name__ == "__main__":
    app.run(port=5000, debug=True)