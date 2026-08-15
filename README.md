# ConsultBae - AI Automation Assignment (Tasks 1-5)

**Author**: Anchal Prasad  
**Date**: August 2026  
**Repository**: https://github.com/Anchal-Prasad/AudioAutomation

---

## Overview

This repository contains the complete solution for the ConsultBae AI Automation Assignment. The project is divided into three core technical tasks and two analytical reports:

- **Task 1**: Merging 3 messy CSV datasets into a single, clean SQLite database with intelligent entity resolution.
- **Task 2**: Building a no-code/low-code automation using n8n (LLM skill categorization).
- **Task 3**: Developing a full-stack audio collection web app (React + FastAPI) that extracts audio properties.
- **Task 4**: A comprehensive report on data quality issues found in the source files.
- **Task 5**: A stretch analysis on scaling the audio app to 5,000 concurrent users.

---

## Setup & Installation

### Prerequisites
- **Python 3.10+** (Install from python.org)
- **Node.js 18+** (Install from nodejs.org)
- **FFmpeg** (Required for audio processing)
- **Git**
- **Task1 - Prerequisites [pip install -r requirements.txt]**
  - pandas>=2.0
  - SQLAlchemy>=2.0
  - psycopg2-binary>=2.9
- **Task3 - Prerequisites [pip install -r requirements.txt]**
  - fastapi
  - uvicorn
  - python-multipart
  - pydub
### 1. Install FFmpeg
Audio extraction relies on `ffprobe` and `pydub`. Ensure FFmpeg is installed and added to your system PATH.

- **Windows**: Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `bin` folder to your environment variables.
- **macOS/Linux**: Use `brew install ffmpeg` or `sudo apt install ffmpeg`.

Verify the installation:
```bash
ffmpeg -version
```
## **Task 1 – Data Merging Pipeline**
The merge pipeline (merge_pipeline.py) ingests source1_naukri_applicants.csv, source2_gig_workers.csv, and source3_cbnexus_contacts.csv into a single SQLite database.

Matching Strategy:

High Confidence: Match by normalized email (S1 ↔ S2) and phone numbers (S1 ↔ S3).

Low Confidence: Fuzzy match by normalized name + city to catch cross-file duplicates without common identifiers.

Conflict Resolution: Ambiguous name+city collisions (e.g., multiple "Arjun Mehta" records) are not auto-merged; they are flagged for manual review (needs_review = True) to prevent false positives.

## **Task 2 – n8n Automation (Skill Auto-Tagger)**
A no-code workflow was built using n8n and Groq LLM to automatically categorize each person's skill set.

Trigger: Manual trigger (or could be set to run periodically).

Logic:

Fetches untagged people from the database via a local Flask API (db_api.py).

Sends the combined skills (from S1 and S2) to Groq's Llama model with a prompt to classify into automation-heavy, web dev, data, design, or other.

Writes the predicted category back to the people.skill_category column.

File: n8n_skill_tagging_workflow.json

## **Task 3 – Audio Collection Web App**
A miniature full-stack application allows gig workers to submit audio recordings. It extracts and stores technical audio properties automatically.

Features:

Input: User Name and Phone Number.

Audio Upload: Record directly in the browser (via WebRTC) or upload an audio file (.mp3, .wav, .webm, etc.).

Processing: On submission, the backend uses ffprobe and pydub to extract:

Duration (seconds)

Sample Rate (Hz)

Bitrate (kbps)

Loudness (dBFS)

A rough quality estimate (ok, quiet, loud, silent).

Storage: Audio files are saved locally, and metadata is stored in consultbae.db linked to the people table.

Dashboard: A "Submissions" view lists all recordings with inline audio playback and extracted properties.

# Task 4 – Data Issues Report

## Data Quality Issues & Normalization Strategies

The following data quality issues were identified across the three source CSV files. Each issue was handled through a specific normalization, validation, or deduplication strategy to produce a consistent unified dataset.

| # | Data Issue | Source(s) | Resolution / Normalization Strategy |
|---:|---|:---:|---|
| 1 | **Phone numbers in Excel scientific notation** (e.g., `9.19E+11`) | S1, S3 | Read CSV files with `dtype=str`; `normalize_phone()` extracts only digits and keeps the last 10 digits. |
| 2 | **Inconsistent phone formats** (e.g., `+91-9000...`, `919000...`) | S1, S3 | Removed all non-digit characters and normalized phone numbers to 10-digit local numbers. |
| 3 | **Negative phone numbers** (e.g., `-9000000040`) | S3 | Removed the `-` character during digit extraction. |
| 4 | **Email casing inconsistency** | S1, S2 | `normalize_email()` converts email addresses to lowercase for consistent matching and deduplication. |
| 5 | **City name variants** (e.g., `Gurugram`, `GURGAON`, `gurugram`) | S1, S2, S3 | `clean_city_display()` standardizes city display names, e.g., to `Gurugram`. |
| 6 | **Multiple date formats** (e.g., `24-07-2026`, `07/13/2026`, `7 Jul 2026`) | S1 | `parse_applied_date()` attempts four supported date-format patterns sequentially. |
| 7 | **Mixed CTC units** (e.g., `4.2` as Lakhs vs `417964` as INR) | S1 | `normalize_ctc()` detects values below `1000` and interprets them as Lakhs by multiplying by `100,000`. |
| 8 | **Mixed rate units** (e.g., `1415/hr` vs `15k/month`) | S2 | `parse_rate()` separates the amount and unit and handles `k` multipliers. |
| 9 | **Status casing inconsistency** (e.g., `Active`, `ACTIVE`, `active`) | S2 | `normalize_status()` converts status values to lowercase. |
| 10 | **Verified field encoded in multiple ways** (`Y`, `y`, `Yes`, `yes`, `N`, `n`, `No`, `no`) | S3 | `normalize_verified()` maps all supported representations to boolean `True` or `False`. |
| 11 | **Skill casing inconsistency** (e.g., `n8n` vs `N8N`) | S1, S2 | `normalize_skills()` converts skills to lowercase and removes duplicate values. |
| 12 | **Intra-file duplicates** (e.g., same phone number with different names) | S1 | Records were grouped by phone number and merged. The row containing the fullest name was preferred, e.g., `Rohit Verma` over `R. Verma`. |
| 13 | **Namesake collisions** (e.g., multiple `Arjun Mehta` records) | S1, S3 | Name + City matching is used only when exactly one candidate exists. Multiple candidates are flagged for review instead of being automatically merged. |
| 14 | **Corrupted rows in S2** (e.g., blank row, comma inside `email_id`) | S2 | Invalid/corrupted rows were filtered out during parsing. |
| 15 | **Embedded header row in S3** | S3 | Rows where `Name == 'Name'` were identified and removed. |
| 16 | **Phone conflicts across different people** (e.g., `9000000170` shared by Varun Saxena and Vikram Mehta) | S1, S3 | `_names_plausibly_match()` requires at least one shared name token before accepting a phone-based match. |
| 17 | **Delhi naming variants** (`Delhi`, `New Delhi`, `Delhi NCR`) | S1, S2, S3 | Original display names are preserved, while the values are folded into `delhi_region` for fuzzy matching purposes. |

## Key Data Cleaning Principles

The normalization process follows these principles:

1. **Preserve original information where possible** rather than unnecessarily overwriting source values.
2. **Normalize values used for matching** so that formatting differences do not create false mismatches.
3. **Avoid aggressive automatic merging** when multiple possible candidates exist.
4. **Flag ambiguous matches for review** instead of making potentially incorrect assumptions.
5. **Handle malformed and corrupted records explicitly** during ingestion.
6. **Standardize units and representations** before performing comparisons or calculations.
7. **Maintain consistent canonical representations** for fields such as phone numbers, emails, cities, skills, dates, and verification status.

## Source Files

| Source | Description |
|---|---|
| **S1** | Source CSV containing candidate/recruitment data |
| **S2** | Source CSV containing additional candidate/work-related data |
| **S3** | Source CSV containing verification/profile-related data |

## Outcome

The cleaning and normalization pipeline converts inconsistent records from the three source systems into a more consistent dataset suitable for **deduplication, entity matching, merging, and downstream automation**.

## **Task 5 – Scaling the Audio App to 5,000 Users (Stretch)**
Scenario: The audio app is deployed to 5,000 gig workers over a single weekend.

What Breaks First?
1. Storage: Local disk runs out of space (5,000 files × 1MB ≈ 5GB+).

2. Processing Bottleneck: The server uses pydub (in-memory decoding) synchronously. Concurrent uploads will cause timeouts and crash the server.

3. Concurrency Limits: The default uvicorn setup cannot handle thousands of simultaneous connections.

4. Network Failures: Users with slow/mobile networks will experience dropped uploads (no resumable logic).

5. Duplicate Submissions: Without authentication/rate-limiting, the same user may spam submissions.

**Proposed Changes Before Launch**
1. Storage: Migrate from local disk to cloud object storage (AWS S3 / Cloudflare R2) with pre-signed URLs for direct uploads from the frontend.

2. Async Processing: Implement a job queue (Redis + Celery) to handle audio extraction asynchronously. Users receive a "processing" status while workers process the file in the background.

3. Scaling Backend: Deploy behind a load balancer with horizontal scaling (Kubernetes or Docker Swarm) and increase uvicorn workers.

4. Resumable Uploads: Implement chunked uploads (TUS protocol) to handle flaky connections.

5. Rate Limiting: Enforce a max submission limit per IP/Phone (e.g., 5 per day) and add OTP verification for real users.

6. Cost & Monitoring: Set up budget alerts, auto-delete old recordings (>30 days), and use structured logging (Sentry/Prometheus) for error tracking.

## **Stuck Log (How I Got Unstuck)**
During the development of this assignment, I encountered several blockers. Here is how I resolved them:

1. FFmpeg Not Found in VS Code Terminal (FileNotFoundError)
The Problem: Running python audio_utils.py resulted in FileNotFoundError: [WinError 2] The system cannot find the file specified for ffprobe. While ffmpeg worked in the system PowerShell, it was not recognized in the VS Code integrated terminal.

What I Searched: "ffmpeg not recognized in vscode terminal", "vscode terminal not picking up path environment variables".

How I Fixed It: I realized VS Code caches environment variables at startup. Simply installing FFmpeg was not enough; I had to fully exit VS Code (File -> Exit) and restart it to reload the system PATH. Additionally, I manually added the bin folder to the PATH using $env:Path += ";C:\...\bin" to test immediately without restarting.

What I Rejected: I initially tried modifying the Python script to use the absolute path to ffprobe.exe. I rejected this because it would break on other machines and is considered a bad practice (hardcoding paths).

2. uvicorn Command Not Found
The Problem: pip install uvicorn succeeded, but typing uvicorn main:app returned "uvicorn is not recognized".

What I Searched: "uvicorn command not found windows", "python -m uvicorn".

How I Fixed It: The Python Scripts folder was not in my PATH. Instead of fixing the PATH globally, I simply used the module syntax: python -m uvicorn main:app --reload --port 8000. This runs Uvicorn reliably regardless of system PATH settings.

3. Task 3 Backend Could Not Find normalize Module
The Problem: The main.py file in Task 3 attempted from normalize import normalize_phone, but the file lived in the task1 directory.

What I Searched: "python import from parent directory", "sys.path.insert".

How I Fixed It: I noticed the code already used sys.path.insert(0, os.path.join(BACKEND_DIR, "..", "..", "task1")). However, I had to ensure that the normalize.py file actually existed in ../task1/. I created a dummy normalize.py with the normalize_phone function to satisfy the dependency and allow the audio app to start.

# **Submission Links**
GitHub Repository: [Insert your GitHub Repo URL]

Screen Recording: 
- Task 1,3: https://youtu.be/QYLRxVsmNTI [Youtube]
- Task 2: https://youtu.be/stVcxDtRtAQ [Youtube]

