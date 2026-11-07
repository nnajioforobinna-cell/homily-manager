"""
Homily Manager - fill in the scripture readings from the homily text.

The import brought the text of each homily in, but the readings a homily was
built on are usually written inside that text rather than in the file name. This
reads the text, finds the scripture citations, and records the most likely
first reading, psalm, second reading, and gospel for each homily.

It is a best-effort first pass (specification section 10, point 5): it fills the
readings so the library can be searched by passage, and so each homily shows its
texts, but the priest can correct any it read wrongly. It only fills homilies
that have no readings yet, so it never overwrites a reading entered by hand, and
re-running is safe.

Run it on its own:
    python extract_readings.py
"""

import os
import re
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "database", "homilies.db")

# Canonical book names, and the abbreviations/variants seen in the homilies.
# Order matters: longer, more specific keys are matched before shorter ones.
BOOK_CANON = [
    # Gospels
    ("Matthew", ["Matthew", "Matt", "Mt"]),
    ("Mark", ["Mark", "Mk"]),
    ("Luke", ["Luke", "Lk"]),
    ("John", ["John", "Jn"]),          # the letters 1/2/3 John are handled below
    # Acts and the epistles (second reading / NT non-gospel)
    ("Acts", ["Acts"]),
    ("Romans", ["Romans", "Rom"]),
    ("1 Corinthians", ["1 Corinthians", "1 Cor", "I Corinthians", "1Cor"]),
    ("2 Corinthians", ["2 Corinthians", "2 Cor", "II Corinthians", "2Cor"]),
    ("Galatians", ["Galatians", "Gal"]),
    ("Ephesians", ["Ephesians", "Eph"]),
    ("Philippians", ["Philippians", "Phil"]),
    ("Colossians", ["Colossians", "Col"]),
    ("1 Thessalonians", ["1 Thessalonians", "1 Thess", "1 Thes"]),
    ("2 Thessalonians", ["2 Thessalonians", "2 Thess", "2 Thes"]),
    ("1 Timothy", ["1 Timothy", "1 Tim"]),
    ("2 Timothy", ["2 Timothy", "2 Tim"]),
    ("Titus", ["Titus"]),
    ("Philemon", ["Philemon", "Philem"]),
    ("Hebrews", ["Hebrews", "Heb"]),
    ("James", ["James", "Jas"]),
    ("1 Peter", ["1 Peter", "1 Pet", "1 Pt"]),
    ("2 Peter", ["2 Peter", "2 Pet", "2 Pt"]),
    ("1 John", ["1 John", "1 Jn"]),
    ("2 John", ["2 John", "2 Jn"]),
    ("3 John", ["3 John", "3 Jn"]),
    ("Jude", ["Jude"]),
    ("Revelation", ["Revelation", "Rev", "Apocalypse"]),
    # Psalms
    ("Psalm", ["Psalms", "Psalm", "Ps"]),
    # Old Testament (first reading)
    ("Genesis", ["Genesis", "Gen"]),
    ("Exodus", ["Exodus", "Exod", "Ex"]),
    ("Leviticus", ["Leviticus", "Lev"]),
    ("Numbers", ["Numbers", "Num"]),
    ("Deuteronomy", ["Deuteronomy", "Deut"]),
    ("Joshua", ["Joshua", "Josh"]),
    ("Judges", ["Judges", "Judg"]),
    ("Ruth", ["Ruth"]),
    ("1 Samuel", ["1 Samuel", "1 Sam"]),
    ("2 Samuel", ["2 Samuel", "2 Sam"]),
    ("1 Kings", ["1 Kings", "1 Kgs"]),
    ("2 Kings", ["2 Kings", "2 Kgs"]),
    ("1 Chronicles", ["1 Chronicles", "1 Chron", "1 Chr"]),
    ("2 Chronicles", ["2 Chronicles", "2 Chron", "2 Chr"]),
    ("Ezra", ["Ezra"]),
    ("Nehemiah", ["Nehemiah", "Neh"]),
    ("Tobit", ["Tobit", "Tob"]),
    ("Judith", ["Judith", "Jdt"]),
    ("Esther", ["Esther", "Esth"]),
    ("1 Maccabees", ["1 Maccabees", "1 Macc"]),
    ("2 Maccabees", ["2 Maccabees", "2 Macc"]),
    ("Job", ["Job"]),
    ("Proverbs", ["Proverbs", "Prov"]),
    ("Ecclesiastes", ["Ecclesiastes", "Eccl", "Qoheleth"]),
    ("Song of Songs", ["Song of Songs", "Song of Solomon", "Canticle"]),
    ("Wisdom", ["Wisdom", "Wis"]),
    ("Sirach", ["Sirach", "Ecclesiasticus", "Sir"]),
    ("Isaiah", ["Isaiah", "Isa"]),
    ("Jeremiah", ["Jeremiah", "Jer"]),
    ("Lamentations", ["Lamentations", "Lam"]),
    ("Baruch", ["Baruch", "Bar"]),
    ("Ezekiel", ["Ezekiel", "Ezek", "Ez"]),
    ("Daniel", ["Daniel", "Dan"]),
    ("Hosea", ["Hosea", "Hos"]),
    ("Joel", ["Joel"]),
    ("Amos", ["Amos"]),
    ("Obadiah", ["Obadiah", "Obad"]),
    ("Jonah", ["Jonah", "Jon"]),
    ("Micah", ["Micah", "Mic"]),
    ("Nahum", ["Nahum", "Nah"]),
    ("Habakkuk", ["Habakkuk", "Hab"]),
    ("Zephaniah", ["Zephaniah", "Zeph"]),
    ("Haggai", ["Haggai", "Hag"]),
    ("Zechariah", ["Zechariah", "Zech"]),
    ("Malachi", ["Malachi", "Mal"]),
]

GOSPELS = {"Matthew", "Mark", "Luke", "John"}
NT_SECOND = {
    "Acts", "Romans", "1 Corinthians", "2 Corinthians", "Galatians",
    "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
    "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon",
    "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
    "Jude", "Revelation",
}

# Build one alternation of every variant, longest first so "1 Corinthians"
# wins over "1 Cor" and "Corinthians". Each variant maps back to its canon.
_VARIANTS = []
for canon, variants in BOOK_CANON:
    for v in variants:
        _VARIANTS.append((v, canon))
_VARIANTS.sort(key=lambda p: len(p[0]), reverse=True)
_ALT = "|".join(re.escape(v) for v, _ in _VARIANTS)
_VAR_TO_CANON = {v.lower(): canon for v, canon in _VARIANTS}

# A citation: a book variant, then a chapter and optional verses. The chapter is
# required so a bare "John" (a person's name, say) is not taken as a citation.
CITE_RE = re.compile(
    r"\b(" + _ALT + r")\b\.?\s*"
    r"(\d{1,3}(?:\s*[:,.]\s*\d{1,3}(?:\s*[\-–]\s*\d{1,3})?)?"
    r"(?:\s*,\s*\d{1,3}(?:\s*[\-–]\s*\d{1,3})?)*)",
    re.IGNORECASE,
)

# A clean, explicit reading list, e.g.
#   "Readings: 1st: Job 3, 1.8-11; Ps. 106; 2nd: 2 Cor. 5, 14-17; Gospel Mk 4: 35-41"
READINGS_LINE_RE = re.compile(r"readings?\s*:?\s*(.+)", re.IGNORECASE)


def _canon(book_variant):
    return _VAR_TO_CANON.get(book_variant.lower())


def normalize_citation(book_variant, tail):
    """Canonical book name + a tidied chapter/verse tail."""
    canon = _canon(book_variant)
    tail = re.sub(r"\s+", "", tail)
    tail = tail.replace("–", "-")
    return f"{canon} {tail}".strip()


def _category(canon):
    if canon == "Psalm":
        return "psalm"
    if canon in GOSPELS:
        return "gospel"
    if canon in NT_SECOND:
        return "second_reading"
    return "first_reading"   # Old Testament


def _verse_span(tail):
    """A rough size of a citation's verse range, so "4:26-34" (the whole
    assigned reading) is preferred over a one-verse "4:26" quoted in passing.
    Only the verses count - the chapter number is dropped so a high chapter
    like 38 does not masquerade as a wide range."""
    if ":" in tail:
        after = tail.split(":", 1)[1]
    elif "," in tail:          # European "chapter, verse" style, e.g. "5, 14-17"
        after = tail.split(",", 1)[1]
    else:
        return 0
    nums = [int(n) for n in re.findall(r"\d+", after)]
    return (max(nums) - min(nums)) if len(nums) >= 2 else 0


def extract_readings(body):
    """Return a dict {role: citation} of the readings most likely assigned to
    this homily, read from its text. Roles not found are left out.

    The assigned reading of each role is almost always the book the homily
    dwells on, so within a role the most-cited book wins; within that book the
    citation with the widest verse range (the fullest reference) is kept.
    """
    if not body:
        return {}
    # role -> book -> list of (citation, position, span)
    buckets = {}
    for m in CITE_RE.finditer(body):
        canon = _canon(m.group(1))
        if not canon:
            continue
        role = _category(canon)
        citation = normalize_citation(m.group(1), m.group(2))
        span = _verse_span(m.group(2))
        buckets.setdefault(role, {}).setdefault(canon, []).append(
            (citation, m.start(), span))

    result = {}
    for role, books in buckets.items():
        # the book of this role the homily engages most (ties: earliest seen)
        best_book = max(
            books, key=lambda b: (len(books[b]), -min(p for _c, p, _s in books[b])))
        cites = books[best_book]
        # the fullest reference to that book (ties: earliest)
        citation, _pos, _span = max(cites, key=lambda c: (c[2], -c[1]))
        result[role] = citation
    return result


def backfill_readings(db_path=None, overwrite=False):
    """Fill readings for homilies that have none. Returns a summary dict."""
    db_path = db_path or os.environ.get("HOMILY_DB", DEFAULT_DB)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        "SELECT id, body FROM homilies WHERE body IS NOT NULL").fetchall()
    summary = {"considered": 0, "filled": 0, "skipped_has_readings": 0,
               "no_citation": 0, "roles_written": 0}

    for r in rows:
        summary["considered"] += 1
        has = db.execute(
            "SELECT 1 FROM readings WHERE homily_id = ? LIMIT 1", (r["id"],)
        ).fetchone()
        if has and not overwrite:
            summary["skipped_has_readings"] += 1
            continue
        readings = extract_readings(r["body"])
        if not readings:
            summary["no_citation"] += 1
            continue
        if overwrite:
            db.execute("DELETE FROM readings WHERE homily_id = ?", (r["id"],))
        for role, citation in readings.items():
            db.execute(
                "INSERT INTO readings (homily_id, role, citation) "
                "VALUES (?, ?, ?)", (r["id"], role, citation))
            summary["roles_written"] += 1
        summary["filled"] += 1

    db.commit()
    db.close()
    return summary


if __name__ == "__main__":
    print("Reading the scripture citations out of each homily's text...\n")
    s = backfill_readings()
    print(f"Considered {s['considered']} homilies with text.")
    print(f"  Filled readings for: {s['filled']}  ({s['roles_written']} readings)")
    print(f"  Already had readings, left alone: {s['skipped_has_readings']}")
    print(f"  No citation found in the text: {s['no_citation']}")
