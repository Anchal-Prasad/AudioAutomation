"""
ConsultBae Task 3 — Mini Audio Collection App (backend)

Run: uvicorn main:app --reload --port 8000
"""
import os
import sys
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from audio_utils import extract_audio_properties

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BACKEND_DIR, "..", "..", "task1", "consultbae.db")
UPLOAD_DIR = os.path.join(BACKEND_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

sys.path.insert(0, os.path.join(BACKEND_DIR, "..", "..", "task1"))
from normalize import normalize_phone  

ALLOWED_EXTENSIONS = {".webm", ".wav", ".mp3", ".ogg", ".m4a"}

app = FastAPI(title="ConsultBae Audio Collection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_con():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def ensure_tables(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS audio_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            submitted_name TEXT,
            submitted_phone TEXT,
            file_path TEXT NOT NULL,
            duration_sec REAL,
            sample_rate_hz INTEGER,
            bitrate_kbps REAL,
            loudness_db REAL,
            quality_note TEXT,
            submitted_at TEXT,
            FOREIGN KEY (person_id) REFERENCES people(person_id)
        )
    """)
    con.commit()


@app.on_event("startup")
def startup():
    if not os.path.exists(DB_PATH):
        raise RuntimeError(
            f"consultbae.db not found at {DB_PATH} — run task1/merge_pipeline.py first."
        )
    con = get_con()
    ensure_tables(con)
    con.close()


def find_or_create_person(con, name: str, phone: str) -> int:
    phone_norm = normalize_phone(phone)
    if phone_norm:
        row = con.execute(
            "SELECT person_id FROM people WHERE primary_phone = ?", (phone_norm,)
        ).fetchone()
        if row:
            return row["person_id"]

    cur = con.execute(
        """INSERT INTO people (canonical_name, primary_phone, match_confidence,
                                needs_review, review_note, sources)
           VALUES (?, ?, 'new', 0, 'created from Task 3 audio submission', 'task3_audio_app')""",
        (name.strip(), phone_norm),
    )
    con.commit()
    return cur.lastrowid


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/submissions")
async def create_submission(
    name: str = Form(...),
    phone: str = Form(...),
    audio: UploadFile = File(...),
):
    ext = os.path.splitext(audio.filename or "")[1].lower() or ".webm"
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported audio format: {ext}")

    safe_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    try:
        props = extract_audio_properties(dest_path)
    except Exception as e:
        os.remove(dest_path)
        raise HTTPException(422, f"Could not process audio file: {e}")

    con = get_con()
    try:
        person_id = find_or_create_person(con, name, phone)
        cur = con.execute(
            """INSERT INTO audio_submissions
               (person_id, submitted_name, submitted_phone, file_path,
                duration_sec, sample_rate_hz, bitrate_kbps, loudness_db,
                quality_note, submitted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                person_id, name.strip(), phone.strip(), safe_filename,
                props["duration_sec"], props["sample_rate_hz"],
                props["bitrate_kbps"], props["loudness_db"],
                props["quality_note"], datetime.now(timezone.utc).isoformat(),
            ),
        )
        con.commit()
        submission_id = cur.lastrowid
    finally:
        con.close()

    return {"id": submission_id, "person_id": person_id, **props, "file_path": safe_filename}


@app.get("/submissions")
def list_submissions():
    con = get_con()
    rows = con.execute("""
        SELECT s.id, s.person_id, s.submitted_name, s.submitted_phone, s.file_path,
               s.duration_sec, s.sample_rate_hz, s.bitrate_kbps, s.loudness_db,
               s.quality_note, s.submitted_at, p.canonical_name
        FROM audio_submissions s
        LEFT JOIN people p ON p.person_id = s.person_id
        ORDER BY s.submitted_at DESC
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


@app.get("/audio/{filename}")
def get_audio(filename: str):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "audio file not found")
    return FileResponse(path)