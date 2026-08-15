"""
Test suite for merge_pipeline.py — run this AFTER merge_pipeline.py.
Covers: row conservation, referential integrity, uniqueness invariants,
the specific trap cases, and idempotency.
"""
import subprocess
import sqlite3
import os
import sys
import pandas as pd
from normalize import normalize_phone, normalize_email

FAILS = []

def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILS.append(name)


# ---------------------------------------------------------------------
# Run the pipeline fresh
# ---------------------------------------------------------------------
if os.path.exists('consultbae.db'):
    os.remove('consultbae.db')
result = subprocess.run([sys.executable, 'merge_pipeline.py'], capture_output=True, text=True)
check("pipeline runs without error", result.returncode == 0, result.stderr[-500:])

con = sqlite3.connect('consultbae.db')
con.row_factory = sqlite3.Row

# ---------------------------------------------------------------------
# 1. ROW CONSERVATION — every input row is accounted for, none silently lost
# ---------------------------------------------------------------------
s1 = pd.read_csv('source1_naukri_applicants.csv')
s2 = pd.read_csv('source2_gig_workers.csv')
s3 = pd.read_csv('source3_cbnexus_contacts.csv')

# NOTE: dtype={'Phone': str} matters here too — without it, pandas infers the
# whole Phone column as float64 (because of Excel scientific-notation values
# like "9.19E+11" mixed in), which corrupts every phone number and makes this
# "expected" count wrong in the same way the old pipeline bug was wrong. Read
# it exactly the way merge_pipeline.py does, or this check just compares the
# bug against itself.
s1 = pd.read_csv('source1_naukri_applicants.csv', dtype={'Phone': str})
s1['phone_norm'] = s1['Phone'].apply(normalize_phone)
# Rows with an unparseable phone can't be grouped on phone_norm (nothing safe
# to key on), so the pipeline gives each of those its own person/row — expect
# one naukri row per unique valid phone, PLUS one per unparseable-phone row.
s1_expected_rows = s1['phone_norm'].nunique(dropna=True) + s1['phone_norm'].isna().sum()
naukri_count = con.execute("SELECT COUNT(*) FROM naukri_applications").fetchone()[0]
check("S1: every unique phone (+ each unparseable-phone row) -> exactly one naukri_applications row",
      naukri_count == s1_expected_rows,
      f"{naukri_count} rows vs {s1_expected_rows} expected in {len(s1)} raw rows")

# S2: count valid rows (drop blank and corrupted)
s2_clean_rows = []
for idx, row in s2.iterrows():
    if row.isna().all():
        continue
    if isinstance(row['email_id'], str) and ',' in row['email_id']:
        continue
    s2_clean_rows.append(row)
gig_count = con.execute("SELECT COUNT(*) FROM gig_worker_profiles").fetchone()[0]
# The number of gig profiles cannot exceed the number of valid S2 rows
# (duplicate emails are merged, so it will be <=)
check("S2: gig profiles count does not exceed valid rows",
      gig_count <= len(s2_clean_rows),
      f"{gig_count} profiles vs {len(s2_clean_rows)} valid rows")

s3_clean = s3[s3['Name'] != 'Name']
cbnexus_count = con.execute("SELECT COUNT(*) FROM cbnexus_contacts").fetchone()[0]
check("S3: every non-header row accounted for",
      cbnexus_count == len(s3_clean),
      f"{cbnexus_count} cbnexus rows vs {len(s3_clean)} non-header S3 rows")

# ---------------------------------------------------------------------
# 2. REFERENTIAL INTEGRITY — no orphan rows, no dangling person_ids
# ---------------------------------------------------------------------
for table in ['naukri_applications', 'gig_worker_profiles', 'cbnexus_contacts',
              'person_emails', 'person_city_variants']:
    orphans = con.execute(f"""
        SELECT COUNT(*) FROM {table} t
        LEFT JOIN people p ON t.person_id = p.person_id
        WHERE p.person_id IS NULL
    """).fetchone()[0]
    check(f"{table}: no orphaned person_id references", orphans == 0, f"{orphans} orphans found")

null_pid = con.execute("SELECT COUNT(*) FROM people WHERE person_id IS NULL").fetchone()[0]
check("people: no NULL person_id", null_pid == 0)

# ---------------------------------------------------------------------
# 3. UNIQUENESS INVARIANTS — a phone/email should map to exactly one person
# ---------------------------------------------------------------------
dupe_phone = con.execute("""
    SELECT primary_phone, COUNT(*) c FROM people
    WHERE primary_phone IS NOT NULL GROUP BY primary_phone HAVING c > 1
""").fetchall()
check("no two people share the same primary_phone", len(dupe_phone) == 0,
      f"{[dict(r) for r in dupe_phone]}")

dupe_email = con.execute("""
    SELECT email, COUNT(DISTINCT person_id) c FROM person_emails GROUP BY email HAVING c > 1
""").fetchall()
check("no email is attached to more than one person", len(dupe_email) == 0,
      f"{[dict(r) for r in dupe_email]}")

# ---------------------------------------------------------------------
# 4. SPECIFIC TRAP CASES — the ones we designed the algorithm around
# ---------------------------------------------------------------------
arjun = con.execute("SELECT * FROM people WHERE canonical_name LIKE '%Arjun Mehta%'").fetchall()
check("Arjun Mehta: exactly 4 distinct people (namesake collision NOT wrongly merged)",
      len(arjun) == 4, f"found {len(arjun)}")
check("Arjun Mehta: all 4 flagged needs_review",
      all(r['needs_review'] == 1 for r in arjun))

deepak = con.execute("SELECT * FROM people WHERE canonical_name LIKE '%Deepak Nair%'").fetchall()
check("Deepak Nair: exactly 2 distinct people", len(deepak) == 2, f"found {len(deepak)}")

meera_id = con.execute("SELECT person_id FROM people WHERE canonical_name LIKE '%Meera Bhatia%'").fetchone()[0]
meera_cities = con.execute("SELECT DISTINCT city_raw FROM person_city_variants WHERE person_id=?", (meera_id,)).fetchall()
check("Meera Bhatia: all 3 conflicting city labels preserved",
      len(meera_cities) == 3, f"found {[r[0] for r in meera_cities]}")

nikhil_id = con.execute("SELECT person_id FROM people WHERE canonical_name LIKE '%Nikhil Chopra%'").fetchone()[0]
nikhil_emails = con.execute("SELECT email FROM person_emails WHERE person_id=?", (nikhil_id,)).fetchall()
check("Nikhil Chopra: both email aliases merged into one person", len(nikhil_emails) == 2)

rohit_verma = con.execute("SELECT * FROM people WHERE canonical_name = 'Rohit Verma'").fetchall()
check("R.Verma/Rohit Verma duplicate: collapsed to exactly 1 person (Rohit Verma)",
      len(rohit_verma) == 1, f"found {len(rohit_verma)}")

# ---------------------------------------------------------------------
# 5. IDEMPOTENCY — running twice should give identical results
# ---------------------------------------------------------------------
first_count = con.execute("SELECT COUNT(*) FROM people").fetchone()[0]
first_review = con.execute("SELECT COUNT(*) FROM people WHERE needs_review=1").fetchone()[0]
con.close()

result2 = subprocess.run([sys.executable, 'merge_pipeline.py'], capture_output=True, text=True)
con2 = sqlite3.connect('consultbae.db')
second_count = con2.execute("SELECT COUNT(*) FROM people").fetchone()[0]
second_review = con2.execute("SELECT COUNT(*) FROM people WHERE needs_review=1").fetchone()[0]
con2.close()

check("idempotent: same total people count on re-run", first_count == second_count,
      f"{first_count} vs {second_count}")
check("idempotent: same needs_review count on re-run", first_review == second_review,
      f"{first_review} vs {second_review}")


print(f"\n{'='*50}")
if FAILS:
    print(f"{len(FAILS)} CHECK(S) FAILED: {FAILS}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")