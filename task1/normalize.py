"""
Normalization helpers for the merge pipeline.
Each function documents WHICH data issue 
"""
import re
from datetime import datetime

def normalize_phone(raw):
    if raw is None or (isinstance(raw, float) and str(raw) == 'nan'):
        return None
    digits = re.sub(r'\D', '', str(raw))
    if len(digits) < 10:
        return None
    return digits[-10:] 


def normalize_email(raw):
    if raw is None or (isinstance(raw, float) and str(raw) == 'nan'):
        return None
    return str(raw).strip().lower()

_CITY_RENAME_MAP = {
    'gurgaon': 'Gurugram',
    'gurugram': 'Gurugram',
    'bangalore': 'Bengaluru',
    'bengaluru': 'Bengaluru',
    'noida': 'Noida',
    'pune': 'Pune',
    'delhi': 'Delhi',
    'new delhi': 'New Delhi',
    'delhi ncr': 'Delhi NCR',
}
def clean_city_display(raw):
    """For storage/display: strip whitespace, fix casing/renames, but do NOT
    collapse Delhi / New Delhi / Delhi NCR into one — those are kept distinct
    since they aren't strictly the same thing (see Task 4 issue #17/#18)."""
    if raw is None:
        return None
    key = str(raw).strip().lower()
    return _CITY_RENAME_MAP.get(key, str(raw).strip().title())

def city_match_key(raw):
    """For FUZZY MATCHING only (loose): also folds Delhi variants together,
    since for the purpose of 'is this plausibly the same person', a Delhi/NCR/
    New Delhi mismatch shouldn't block a name-based candidate match."""
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if key in ('gurgaon', 'gurugram'):
        return 'gurugram'
    if key in ('bangalore', 'bengaluru'):
        return 'bengaluru'
    if key in ('delhi', 'new delhi', 'delhi ncr'):
        return 'delhi_region'
    return key

def normalize_name(raw):
    if raw is None:
        return None
    return re.sub(r'\s+', ' ', str(raw)).strip().lower()

def parse_applied_date(raw):
    if raw is None:
        return None
    d = str(raw).strip()
    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%m/%d/%Y', '%d %b %Y'):
        try:
            return datetime.strptime(d, fmt).date().isoformat()
        except ValueError:
            continue
    return None 


def normalize_ctc(raw):
    """Returns (normalized_inr, was_corrected)"""
    if raw is None:
        return None, False
    val = float(raw)
    if val < 1000:  
        return val * 100000, True
    return val, False


def parse_rate(raw):
    """Returns (amount, unit) where unit is 'hour' or 'month'"""
    if raw is None or (isinstance(raw, float) and str(raw) == 'nan'):
        return None, None
    s = str(raw).strip().lower()
    m = re.match(r'([\d.]+)\s*k?\s*/\s*(hr|hour|month|mo)', s)
    if not m:
        return None, None
    amount = float(m.group(1))
    if 'k' in s.split('/')[0]:
        amount *= 1000
    unit = 'hour' if m.group(2) in ('hr', 'hour') else 'month'
    return amount, unit

def normalize_status(raw):
    if raw is None or (isinstance(raw, float) and str(raw) == 'nan'):
        return None
    return str(raw).strip().lower()

def normalize_verified(raw):
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in ('y', 'yes'):
        return True
    if s in ('n', 'no'):
        return False
    return None


def normalize_skills(raw):
    if raw is None or (isinstance(raw, float) and str(raw) == 'nan'):
        return []
    return sorted({s.strip().lower() for s in str(raw).split(',') if s.strip()})

if __name__ == '__main__':
   
    assert normalize_phone('+91-9000000131') == '9000000131'
    assert normalize_phone(919000000254) == '9000000254'
    assert normalize_email('ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG') == 'isha.chopra95@mailtest.example.org'
    assert clean_city_display('gurugram ') == 'Gurugram'
    assert clean_city_display('GURGAON') == 'Gurugram'
    assert city_match_key('New Delhi') == city_match_key('Delhi NCR') == 'delhi_region'
    assert parse_applied_date('07/13/2026') == '2026-07-13'
    assert parse_applied_date('24-07-2026') == '2026-07-24'
    assert parse_applied_date('2026-08-08') == '2026-08-08'
    assert parse_applied_date('7 Jul 2026') == '2026-07-07'
    assert normalize_ctc(4.2) == (420000.0, True)
    assert normalize_ctc(417964) == (417964, False)
    assert parse_rate('1415/hr') == (1415.0, 'hour')
    assert parse_rate('15k/month') == (15000.0, 'month')
    assert normalize_verified('Yes') is True
    assert normalize_verified('N') is False
    print("All normalization sanity checks passed.")