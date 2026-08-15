"""
Task 1 – Merging pipeline
----------------------------------------
The same real person may appear across files with different IDs, so we
match using:
  - email (shared by S1 and S2)
  - phone (shared by S1 and S3)
  - name+city as a low‑confidence fallback (but only when there's exactly
    one candidate – ambiguous cases are flagged for manual review).
"""

import os
import re
import pandas as pd
from sqlalchemy import create_engine, text
from normalize import (
    normalize_phone, normalize_email, clean_city_display, city_match_key,
    normalize_name, parse_applied_date, normalize_ctc, parse_rate,
    normalize_status, normalize_verified, normalize_skills
)

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///consultbae.db')

class Person:
    _next_id = 1

    def __init__(self, name, source):
        self.id = Person._next_id
        Person._next_id += 1

        self.canonical_name = name         
        self.phones = set()                 
        self.emails = set()                 
        self.city_variants = []             
        self.sources = {source}             
        self.match_confidence = 'high'      
        self.needs_review = False          
        self.review_note = None            
        
        self.naukri = None      # S1
        self.gig = None         # S2
        self.cbnexus = None     # S3

    def add_city(self, raw, source):
        """Storing all city string from a given source."""
        if raw:
            self.city_variants.append((raw, source))

    def canonical_city(self):
        """
        Return the best city for display.
        """
        for raw, src in self.city_variants:
            if src == 'S1':
                return clean_city_display(raw)
        if self.city_variants:
            return clean_city_display(self.city_variants[0][0])
        return None


people = []                
phone_index = {}           
email_index = {}           
name_city_index = {}      
log = []                    

def index_person(p):
    """Add a Person to all lookup indexes."""
    for ph in p.phones:
        phone_index[ph] = p
    for em in p.emails:
        email_index[em] = p

    # used city_match_key to fold Delhi variants into one bucket.
    city_keys = {city_match_key(raw) for raw, _ in p.city_variants} or {None}
    for ck in city_keys:
        key = (normalize_name(p.canonical_name), ck)
        name_city_index.setdefault(key, []).append(p)


# -------------------------------------------------------------------------
# STEP 1 – Source 1 (Naukri applicants)
# -------------------------------------------------------------------------
# We load S1 first because it has both email and phone, making it the
# "anchor" that links S2 (email) and S3 (phone).

s1 = pd.read_csv('source1_naukri_applicants.csv', dtype={'Phone': str})
s1['phone_norm'] = s1['Phone'].apply(normalize_phone)

bad_phone = s1[s1['phone_norm'].isna()]
if len(bad_phone):
    log.append(f"S1: {len(bad_phone)} row(s) had an unparseable phone number "
               f"(Excel scientific notation, e.g. '9.19E+11') -> phone_norm=None. "
               f"Each is loaded as its own person (nothing safe to dedupe them on) "
               f"instead of being silently dropped or wrongly collapsed together.")


def _build_naukri_person(row, source_rows):
    """Build a Person from an S1 row. `row` supplies the naukri_applications
    fields (the fuller-name row, for an intra-file duplicate group); `source_rows`
    is every raw S1 row this Person represents, for collecting all emails/cities."""
    p = Person(row['Full Name'], 'S1')
    if pd.notna(row['phone_norm']):
        p.phones.add(row['phone_norm'])

    for _, r in source_rows.iterrows():
        ne = normalize_email(r['Email'])
        if ne:
            p.emails.add(ne)
        p.add_city(r['City'], 'S1')

    ctc_norm, ctc_corrected = normalize_ctc(row['Current CTC'])
    applied = parse_applied_date(row['Applied Date'])
    future_flag = bool(applied and applied > '2026-08-13')  

    p.naukri = {
        'experience_years': row['Experience (Years)'],
        'ctc_inr': ctc_norm,
        'ctc_unit_corrected': ctc_corrected,
        'applied_date': applied,
        'applied_date_future_flag': future_flag,
        'skills': normalize_skills(row['Skills']),
    }

    people.append(p)
    index_person(p)
    return p


s1_with_phone = s1.dropna(subset=['phone_norm'])
for phone, group in s1_with_phone.groupby('phone_norm'):
    if len(group) > 1:
        log.append(f"S1 intra-file duplicate on phone {phone}: "
                   f"{list(group['Full Name'])} -> merged into one record")

    # Picking the row with the fuller name (not abbreviated like "R. Verma").
    row = group.iloc[0]
    for _, r in group.iterrows():
        if not re.match(r'^[A-Z]\.\s', str(r['Full Name'])):
            row = r
            break

    _build_naukri_person(row, group)


for _, row in bad_phone.iterrows():
    _build_naukri_person(row, pd.DataFrame([row]))

log.append(f"STEP 1 done: {len(people)} people loaded from S1 "
           f"(from {len(s1)} raw rows)")


# -------------------------------------------------------------------------
# STEP 2 – Source 2 (gig workers)
# -------------------------------------------------------------------------
# We match by email. If an email is new, we create a new person.
# We must droped the blank row and the corrupted column‑shifted rows.

s2 = pd.read_csv('source2_gig_workers.csv')

s2_clean_rows = []
for idx, row in s2.iterrows():
    if row.isna().all():
        log.append(f"S2 row {idx}: entirely blank -> dropped")
        continue
    if isinstance(row['email_id'], str) and ',' in row['email_id']:
        log.append(f"S2 row {idx}: email_id contains a comma (corrupted) -> dropped")
        continue
    s2_clean_rows.append(row)

s2_clean = pd.DataFrame(s2_clean_rows)

s2_new_count = 0
for _, row in s2_clean.iterrows():
    ne = normalize_email(row['email_id'])  

    # Build the gig data dict (rate, status, skills).
    gig_data = {
        'skill_tags': normalize_skills(row['skill_tags']),
        'status': normalize_status(row['status']),
    }
    amount, unit = parse_rate(row['rate'])
    gig_data['rate_amount'] = amount
    gig_data['rate_unit'] = unit

    if ne in email_index:
        p = email_index[ne]
        p.sources.add('S2')
        p.add_city(row['location'], 'S2')
        p.gig = gig_data
    else:
        p = Person(row['worker_name'], 'S2')
        if ne:  
            p.emails.add(ne)
        p.add_city(row['location'], 'S2')
        p.gig = gig_data
        people.append(p)
        index_person(p)
        s2_new_count += 1

log.append(f"STEP 2 done: matched {len(s2_clean) - s2_new_count} S2 rows to existing people via email, "
           f"{s2_new_count} new S2-only people created")


# -------------------------------------------------------------------------
# STEP 3 – Source 3 (CBNexus contacts)
# -------------------------------------------------------------------------
# We first try to match by phone. If that fails, we fall back to a fuzzy
# name+city match, but we only merge if there is exactly one candidate.
# Ambiguous matches (two or more candidates) create a new person and flag
# all involved records for review.

s3 = pd.read_csv('source3_cbnexus_contacts.csv')
s3_clean = s3[s3['Name'] != 'Name'].copy()
log.append(f"S3: dropped {len(s3) - len(s3_clean)} embedded-header row(s)")

s3_phone_matched = 0
s3_fuzzy_matched = 0
s3_new = 0
s3_ambiguous = 0


def _names_plausibly_match(name_a, name_b):
    """Guard for trusting a phone match: require at least one shared name
    token (first or last name). A shared phone digit-string alone isn't
    enough — phone numbers can coincidentally collide, be reused, or be
    typo'd (e.g. S1's 'Varun Saxena' and S3's 'Vikram Mehta' both normalize
    to 9000000170), and blindly merging on phone would silently attach one
    person's CBNexus record to a completely different person."""
    a = set(normalize_name(name_a).split())
    b = set(normalize_name(name_b).split())
    return bool(a & b)


def _safe_add_phone(p, np_):
    """Add a normalized phone to a person, but never let two different
    people both claim it. If the number is already owned by someone else,
    skip silently rather than overwrite — a conflicting phone should not be
    trusted as a match signal, but it also must not corrupt a second
    person's primary_phone."""
    if np_ is None:
        return
    owner = phone_index.get(np_)
    if owner is not None and owner is not p:
        return
    p.phones.add(np_)
    phone_index[np_] = p


for _, row in s3_clean.iterrows():
    np_ = normalize_phone(row['Phone Number'])  

    cbnexus_data = {
        'verified': normalize_verified(row['Verified']),
        'projects_completed': row['Projects Completed'],
    }
    phone_conflict_note = None  

    if np_ in phone_index:
        candidate = phone_index[np_]
        if _names_plausibly_match(row['Name'], candidate.canonical_name):
            p = candidate
            p.sources.add('S3')
            p.add_city(row['City'], 'S3')
            p.cbnexus = cbnexus_data
            s3_phone_matched += 1
            continue
        else:
            phone_conflict_note = (
                f"Phone {np_} is also on file for '{candidate.canonical_name}', but the "
                f"name here ('{row['Name']}') doesn't match — treated as a coincidental/"
                f"reused number, not auto-merged on phone."
            )
            log.append(f"S3 PHONE CONFLICT: '{row['Name']}' shares phone {np_} with existing "
                       f"person '{candidate.canonical_name}' but names don't match -> "
                       f"ignoring the phone match, falling back to name+city")

    nn = normalize_name(row['Name'])
    ck = city_match_key(row['City'])
    candidates = name_city_index.get((nn, ck), [])

    if len(candidates) == 1:
        p = candidates[0]
        p.sources.add('S3')
        _safe_add_phone(p, np_)
        p.add_city(row['City'], 'S3')
        p.cbnexus = cbnexus_data
        p.match_confidence = 'low'
        p.needs_review = True
        note = 'Matched by name+city only (no phone/email overlap) — verify manually.'
        p.review_note = note if not phone_conflict_note else f"{note} {phone_conflict_note}"
        s3_fuzzy_matched += 1

    elif len(candidates) > 1:
        log.append(f"S3 AMBIGUOUS: '{row['Name']}' in {row['City']} matches {len(candidates)} existing "
                   f"people by name+city alone (namesake collision) — NOT auto-merged, created as separate person")
        p = Person(row['Name'], 'S3')
        _safe_add_phone(p, np_)
        p.add_city(row['City'], 'S3')
        p.cbnexus = cbnexus_data
        p.match_confidence = 'low'
        p.needs_review = True
        note = f'Ambiguous: name+city matched {len(candidates)} existing people, none chosen automatically.'
        p.review_note = note if not phone_conflict_note else f"{note} {phone_conflict_note}"
        for cand in candidates:
            cand.needs_review = True
            cand.review_note = (cand.review_note or '') + ' Possible namesake collision with another record — verify.'
        people.append(p)
        index_person(p)
        s3_ambiguous += 1

    else:
        p = Person(row['Name'], 'S3')
        _safe_add_phone(p, np_)
        p.add_city(row['City'], 'S3')
        p.cbnexus = cbnexus_data
        if phone_conflict_note:
            p.needs_review = True
            p.match_confidence = 'low'
            p.review_note = phone_conflict_note
        people.append(p)
        index_person(p)
        s3_new += 1

log.append(f"STEP 3 done: {s3_phone_matched} matched by phone, {s3_fuzzy_matched} matched by fuzzy name+city "
           f"(flagged low-confidence), {s3_ambiguous} ambiguous namesake cases kept separate, {s3_new} new S3-only people")
log.append(f"TOTAL UNIQUE PEOPLE after merge: {len(people)}")


# -------------------------------------------------------------------------
# LOAD – write all data to the SQLite database
# -------------------------------------------------------------------------
engine = create_engine(DATABASE_URL)
with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS cbnexus_contacts"))
    conn.execute(text("DROP TABLE IF EXISTS gig_worker_profiles"))
    conn.execute(text("DROP TABLE IF EXISTS naukri_applications"))
    conn.execute(text("DROP TABLE IF EXISTS person_emails"))
    conn.execute(text("DROP TABLE IF EXISTS person_city_variants"))
    conn.execute(text("DROP TABLE IF EXISTS people"))

    conn.execute(text("""
        CREATE TABLE people (
            person_id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            primary_phone TEXT,
            primary_email TEXT,
            canonical_city TEXT,
            match_confidence TEXT,
            needs_review INTEGER,
            review_note TEXT,
            sources TEXT
        )
    """))

    conn.execute(text("""
        CREATE TABLE person_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER,
            email TEXT,
            source TEXT
        )
    """))

    conn.execute(text("""
        CREATE TABLE person_city_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER,
            city_raw TEXT,
            source TEXT
        )
    """))

    conn.execute(text("""
        CREATE TABLE naukri_applications (
            person_id INTEGER PRIMARY KEY,
            experience_years REAL,
            ctc_inr REAL,
            ctc_unit_corrected INTEGER,
            applied_date TEXT,
            applied_date_future_flag INTEGER,
            skills TEXT
        )
    """))

    conn.execute(text("""
        CREATE TABLE gig_worker_profiles (
            person_id INTEGER PRIMARY KEY,
            rate_amount REAL,
            rate_unit TEXT,
            status TEXT,
            skill_tags TEXT
        )
    """))

    conn.execute(text("""
        CREATE TABLE cbnexus_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER,
            verified INTEGER,
            projects_completed INTEGER,
            FOREIGN KEY (person_id) REFERENCES people(person_id)
        )
    """))

    for p in people:
        conn.execute(text("""
            INSERT INTO people (
                person_id, canonical_name, primary_phone, primary_email,
                canonical_city, match_confidence, needs_review, review_note, sources
            ) VALUES (:id, :name, :phone, :email, :city, :conf, :review, :note, :src)
        """), {
            'id': p.id,
            'name': p.canonical_name,
            'phone': sorted(p.phones)[0] if p.phones else None,
            'email': sorted(p.emails)[0] if p.emails else None,
            'city': p.canonical_city(),
            'conf': p.match_confidence,
            'review': int(p.needs_review),
            'note': p.review_note,
            'src': ','.join(sorted(p.sources))
        })

        for em in p.emails:
            conn.execute(
                text("INSERT INTO person_emails (person_id, email, source) VALUES (:pid, :em, 'merged')"),
                {'pid': p.id, 'em': em}
            )

        for raw, src in p.city_variants:
            conn.execute(
                text("INSERT INTO person_city_variants (person_id, city_raw, source) VALUES (:pid, :c, :s)"),
                {'pid': p.id, 'c': raw, 's': src}
            )

        if p.naukri:
            conn.execute(text("""
                INSERT INTO naukri_applications
                VALUES (:pid, :exp, :ctc, :corrected, :date, :future, :skills)
            """), {
                'pid': p.id,
                'exp': p.naukri['experience_years'],
                'ctc': p.naukri['ctc_inr'],
                'corrected': int(p.naukri['ctc_unit_corrected']),
                'date': p.naukri['applied_date'],
                'future': int(p.naukri['applied_date_future_flag']),
                'skills': ','.join(p.naukri['skills'])
            })

        if p.gig:
            conn.execute(text("""
                INSERT INTO gig_worker_profiles
                VALUES (:pid, :amt, :unit, :status, :tags)
            """), {
                'pid': p.id,
                'amt': p.gig['rate_amount'],
                'unit': p.gig['rate_unit'],
                'status': p.gig['status'],
                'tags': ','.join(p.gig['skill_tags'])
            })

        if p.cbnexus:
            conn.execute(text("""
                INSERT INTO cbnexus_contacts (person_id, verified, projects_completed)
                VALUES (:pid, :ver, :proj)
            """), {
                'pid': p.id,
                'ver': (None if p.cbnexus['verified'] is None else int(p.cbnexus['verified'])),
                'proj': p.cbnexus['projects_completed']
            })


print("\n".join(log))
print(f"\nLoaded into: {DATABASE_URL}")
print(f"needs_review flagged: {sum(1 for p in people if p.needs_review)} people")