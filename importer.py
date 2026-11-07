"""
Homily Manager - import your existing homilies (specification section 10).

Reads the six year folders and the FUNERAL HOMILIES folder that sit next to the
app folder, and creates one library record per file. It fills in what the folder
and file names already carry - the cycle year, the liturgical day, and the
funeral date and name - and pulls the text of each homily into the record.

Nothing is thrown away. Anything the import is unsure about (a PDF it could not
read, a file that is not a personal homily, a duplicate or variant marked "Old"
or "LATEST") is imported anyway and flagged in `import_note`, so you confirm it
by hand rather than the import guessing.

Re-running is safe: a file already imported (matched by its path) is skipped, so
you can run this again after adding new files.

Run it on its own:
    python importer.py
or use the Import page inside the app.
"""

import os
import re
import sqlite3
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOMILY_ROOT = os.path.dirname(BASE_DIR)  # the "HOMILY MANAGER" folder
DEFAULT_DB = os.path.join(BASE_DIR, "database", "homilies.db")

# The six year folders, each with the Sunday cycle year it holds.
YEAR_FOLDERS = {
    "2020 - 2021 HOMILIES YEAR B": "B",
    "2021 - 2022 HOMILIES YEAR C": "C",
    "2022 - 2023 HOMILIES YEAR A": "A",
    "2023 - 2024 HOMILIES YEAR B": "B",
    "2024 - 2025 HOMILIES YEAR C": "C",
    "2025 - 2026 HOMILIES YEAR A": "A",
}
FUNERAL_FOLDER = "FUNERAL HOMILIES"
WEDDINGS_FOLDER = "WEDDINGS"

READABLE = (".docx", ".doc", ".pdf")

# Wedding files that are a template or collection, not for one couple.
WEDDING_TEMPLATE_HINTS = ("nuptial homily", "wedding homilies", "marriage homilies")

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Markers in a filename that mean "this is a second copy or a variant".
VARIANT_RE = re.compile(
    r"\b(old|latest|draft|copy|final|version|revised)\b", re.IGNORECASE)
# A trailing " 2" / " 3" (a numbered duplicate), or a bare year.
TRAILING_NUM_RE = re.compile(r"\s+\d{1,2}$")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Files in the funeral folder that are not a homily for one named person.
NON_PERSON_HINTS = (
    "reading", "psalm", "prayer of the faithful", "prayers of the faithful",
    "checklist", "check list", "outline", "database", "ideas", "mass outline",
    "wedding & funeral", "funeral homilies", "homily ideas", "obituary", "obit",
    "committal", "cemetery", "stories", "contact form", "rite of",
    "preparation for death", "departure time", "order for",
)

# Words that are never, by themselves, a person's name. Used to throw out junk
# the pattern matcher would otherwise pick up (e.g. "A", "Homily for").
NAME_STOPWORDS = {
    "a", "an", "the", "another", "my", "for", "of", "and", "this", "that",
    "is", "our", "what", "why", "did", "have", "to", "mass", "homily",
    "sermon", "funeral", "burial", "prayer", "prayers",
}
# A real person's name never contains any of these.
BAD_IN_NAME = (
    "funeral", "homily", "sermon", "burial", "mass", "obituary", "obit",
    "prayer", "checklist", "check list", "reading", "committal", "cemetery",
    "ideas", "outline", "database", "rite ", "contact", "departure",
    "preparation",
)


# --------------------------------------------------------------------------
# Text extraction
# --------------------------------------------------------------------------
def normalize(text):
    if not text:
        return ""
    # Unicode line/paragraph separators that Word leaves behind read as no break
    # at all in a browser, so turn them into real newlines.
    text = text.replace(" ", "\n").replace(" ", "\n\n")
    text = text.replace("\xa0", " ").replace("\t", " ").replace("\r", "\n")
    # collapse runs of spaces, but keep paragraph breaks
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(path):
    """Return (text, note). note is set when extraction failed or was partial."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".doc", ".docx"):
        try:
            out = subprocess.run(
                ["textutil", "-convert", "txt", "-stdout", path],
                capture_output=True, text=True, timeout=60)
            if out.returncode == 0 and out.stdout.strip():
                return normalize(out.stdout), None
            return "", "Could not read the text of this file - please open it by hand."
        except Exception:
            return "", "Could not read the text of this file - please open it by hand."
    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
            text = normalize(text)
            if text:
                return text, "Read from a PDF - please check the text came across cleanly."
            return "", "This is a PDF the import could not read - please add the text by hand."
        except Exception:
            return "", "This is a PDF the import could not read - please add the text by hand."
    return "", "Unsupported file type - not imported automatically."


# --------------------------------------------------------------------------
# Filename parsing - shared
# --------------------------------------------------------------------------
def stem(filename):
    return os.path.splitext(filename)[0]


def title_from(name):
    """A readable title: underscores to spaces, tidy whitespace."""
    t = name.replace("_", " ").strip()
    t = re.sub(r"\s{2,}", " ", t)
    return t or "Untitled"


def variant_flag(name):
    marks = []
    m = VARIANT_RE.search(name)
    if m:
        marks.append(m.group(0).lower())
    if TRAILING_NUM_RE.search(name):
        marks.append("numbered copy")
    if marks:
        return ("This looks like a duplicate or variant (" +
                ", ".join(sorted(set(marks))) +
                ") - keep the one you want and archive the rest.")
    return None


# --------------------------------------------------------------------------
# Filename parsing - Sunday / weekday / feast
# --------------------------------------------------------------------------
def detect_season(s):
    s = s.lower()
    if "advent" in s:
        return "advent"
    if "christmas" in s or "nativity" in s or "epiphany" in s or "holy family" in s:
        return "christmas"
    if ("lent" in s or "ash wednesday" in s or "palm sunday" in s
            or "passion" in s or "holy thursday" in s or "good friday" in s):
        return "lent"
    if ("easter" in s or "pentecost" in s or "ascension" in s):
        return "easter"
    if "ordinary" in s or re.search(r"\bord\b", s) or "ord time" in s or "ord." in s:
        return "ordinary_time"
    return None


FEAST_KEYWORDS = (
    "corpus christi", "christ the king", "trinity", "pentecost", "ascension",
    "holy thursday", "good friday", "easter sunday", "palm sunday",
    "ash wednesday", "all saints", "all souls", "immaculate", "assumption",
    "epiphany", "holy family", "baptism of the lord", "presentation",
    "transfiguration", "sacred heart", "annunciation", "christ the king",
)


def parse_sunday(filename, cycle):
    """Parse a file inside a year folder into fields for a homily record."""
    name = stem(filename)
    note_parts = []
    v = variant_flag(name)
    if v:
        note_parts.append(v)

    lowered = name.lower()
    season = detect_season(name)

    if re.search(r"\bweek\b", lowered) and "sunday" not in lowered:
        htype = "weekday"
    elif any(k in lowered for k in FEAST_KEYWORDS) and not re.search(
            r"\b\d{1,2}(st|nd|rd|th)\b", lowered):
        htype = "feast"
    else:
        htype = "sunday"

    # A tidy liturgical-day label: drop the extension, variant words, a bare
    # year, and anything after a " - " that reads like a theme/title.
    day = title_from(name)
    day = YEAR_RE.sub("", day)
    day = VARIANT_RE.sub("", day)
    day = re.sub(r"\s*[-_]\s*$", "", day)
    day = re.sub(r"\s{2,}", " ", day).strip(" -_")

    cycle_year = cycle if htype in ("sunday", "feast") else None
    if htype == "weekday":
        note_parts.append(
            "Weekday cycle (I or II) is not in the file name - set it by hand.")

    return {
        "type": htype,
        "title": title_from(name),
        "liturgical_day": day or None,
        "season": season,
        "cycle_year": cycle_year,
        "import_note": " ".join(note_parts) or None,
    }


# --------------------------------------------------------------------------
# Filename parsing - funerals
# --------------------------------------------------------------------------
def parse_funeral_date(name):
    """Find a 'Nth Month YYYY' date and return it as YYYY-MM-DD, or None."""
    m = re.search(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\.?,?\s+(\d{4})", name)
    if not m:
        return None, None
    day = int(m.group(1))
    month = MONTHS.get(m.group(2).lower())
    year = int(m.group(3))
    if not month:
        return None, None
    try:
        return f"{year:04d}-{month:02d}-{day:02d}", m.span()
    except ValueError:
        return None, m.span()


def parse_deceased_name(name):
    """Pull the person's name out of a funeral filename, or None if it is not a
    homily for one named person. Conservative: when the name is not clear it
    returns None and the file is flagged, rather than guessing a theme as a name.
    """
    work = name.replace("_", " ")
    # remove a date span and surrounding separators
    _, span = parse_funeral_date(work)
    if span:
        work = (work[:span[0]] + " " + work[span[1]:])
    work = re.sub(r"\s{2,}", " ", work).strip(" -,")

    # Most specific first. Each captures the text that should be the name.
    patterns = [
        r"funeral homily (?:mass )?for\s+-?\s*(.+)",
        r"funeral homily of\s+(.+)",
        r"funeral sermon for\s+(.+)",
        r"funeral mass (?:for|of)\s+(.+)",
        r"funeral (?:for|of)\s+-?\s*(.+)",
        r"\bmass (?:for|of)\s+(.+)",
        r"homily for\s+(.+)",
        r"sermon for\s+(.+)",
    ]
    low = work.lower()
    for pat in patterns:
        m = re.search(pat, low)
        if m:
            s, e = m.span(1)
            candidate = _clean_candidate(work[s:e])
            if _looks_like_name(candidate):
                return candidate

    # "NAME funeral sermon" (name comes before the words)
    m = re.search(r"(.+?)\s+funeral (?:sermon|homily)", low)
    if m:
        candidate = _clean_candidate(work[m.span(1)[0]:m.span(1)[1]])
        if _looks_like_name(candidate):
            return candidate

    # When the filename carried a date, it is almost certainly one person's
    # funeral, so accept a name after "(A) Funeral Homily -" that we would
    # otherwise skip as possibly a theme.
    if span:
        m = re.search(r"funeral homily (?:for )?-?\s*(.+)", low)
        if m:
            candidate = _clean_candidate(work[m.span(1)[0]:m.span(1)[1]])
            if _looks_like_name(candidate):
                return candidate

    # A bare name, e.g. "FRANKLYN PATRICK MUNROE" or "Arthur Cecil Martin"
    # (after the date was stripped). This is the loosest case, so also require
    # it to be capitalised like a name - this keeps thematic titles such as
    # "What is our Gain" from being read as a person.
    candidate = _clean_candidate(work)
    if _looks_like_name(candidate) and _is_proper_name_form(candidate):
        return candidate
    return None


def _is_proper_name_form(s):
    """True if every word starts with a capital (bar small particles) - the
    shape a real name takes, unlike a sentence-style title."""
    particles = {"and", "of", "the", "van", "von", "de", "la", "le", "el", "du"}
    for w in re.split(r"[ \-]+", s):
        if not w or w.lower() in particles:
            continue
        if not w[0].isupper():
            return False
    return True


def _clean_candidate(s):
    """Trim a captured span down to the name: drop a trailing theme after ' - '
    and surrounding punctuation."""
    s = re.split(r"\s+-\s+", s)[0]        # "Vadie Thornhill - OUR RETURN" -> name
    s = re.split(r"\s+\d", s)[0]          # drop a trailing stray number
    return s.strip(" -\"'.,")


def _looks_like_name(s):
    if not s:
        return False
    low = s.lower()
    if any(b in low for b in BAD_IN_NAME):
        return False
    if any(h in low for h in NON_PERSON_HINTS):
        return False
    # letters first, then letters/spaces and the punctuation names really use
    if not re.fullmatch(r"[A-Za-z][A-Za-z .,'\"()&\-]*", s):
        return False
    words = [w for w in re.split(r"[ \-]+", low) if w]
    if not words or len(words) > 6:
        return False
    content = [w for w in words if w not in NAME_STOPWORDS]
    if not content:                       # nothing but stopwords ("A", "The")
        return False
    if not any(len(w) >= 2 for w in content):
        return False
    return True


def parse_funeral(filename):
    name = stem(filename)
    note_parts = []
    v = variant_flag(name)
    if v:
        note_parts.append(v)

    date_iso, _ = parse_funeral_date(name)
    deceased = parse_deceased_name(name)

    low = name.lower()
    is_reference = any(h in low for h in NON_PERSON_HINTS) and not deceased
    if is_reference:
        note_parts.append(
            "This is a reference or template, not a homily for one person - "
            "review and file it where it belongs.")
    elif not deceased:
        note_parts.append(
            "Could not read a name from the file name - please add the "
            "deceased's name.")
    if deceased and not date_iso:
        note_parts.append("No funeral date in the file name - please add it.")

    title = title_from(name)
    return {
        "type": "funeral",
        "title": title,
        "deceased_name": deceased,
        "date_of_funeral": date_iso,
        "import_note": " ".join(note_parts) or None,
    }


# --------------------------------------------------------------------------
# Filename parsing - weddings
# --------------------------------------------------------------------------
def parse_wedding(filename):
    name = stem(filename).replace("_", " ")
    note_parts = []
    v = variant_flag(name)
    if v:
        note_parts.append(v)

    low = name.lower()
    couple = None
    is_template = (any(h in low for h in WEDDING_TEMPLATE_HINTS)
                   or low.strip() in ("wedding homily", "marriage homily",
                                       "nuptial homily"))
    if not is_template:
        patterns = [
            r"(?:marriage|wedding|nuptial) homily (?:for )?-?\s*(.+)",
            r"wedding mass (?:for|of)\s+(.+)",
            r"wedding of\s+(.+)",
            r"marriage of\s+(.+)",
        ]
        for pat in patterns:
            m = re.search(pat, low)
            if m:
                cand = _clean_candidate(name[m.span(1)[0]:m.span(1)[1]])
                if _looks_like_name(cand):
                    couple = cand
                    break
        if couple is None:
            cand = _clean_candidate(name)
            if _looks_like_name(cand) and _is_proper_name_form(cand):
                couple = cand

    if is_template:
        note_parts.append(
            "A wedding template or collection, not for one couple.")
    elif not couple:
        note_parts.append(
            "Could not read the couple's names from the file name - please add them.")

    return {
        # a template is filed as 'other' so it stays out of the couples list
        "type": "other" if is_template else "wedding",
        "title": title_from(name),
        "people": couple,
        "import_note": " ".join(note_parts) or None,
    }


# --------------------------------------------------------------------------
# Running the import
# --------------------------------------------------------------------------
def _already_imported(db, source_file):
    row = db.execute(
        "SELECT 1 FROM homilies WHERE source_file = ?", (source_file,)
    ).fetchone()
    return row is not None


def _insert(db, fields, body, source_file):
    cur = db.execute(
        "INSERT INTO homilies (type, title, core_message, body, status, "
        "liturgical_day, season, cycle_year, source_file, import_note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            fields["type"], fields["title"], None, body or None,
            "preached",  # these are all homilies already given
            fields.get("liturgical_day"), fields.get("season"),
            fields.get("cycle_year"), source_file, fields.get("import_note"),
        ),
    )
    return cur.lastrowid


def run_import(db_path=None, root=None):
    """Import every file, skipping ones already imported. Returns a summary dict."""
    db_path = db_path or os.environ.get("HOMILY_DB", DEFAULT_DB)
    root = root or HOMILY_ROOT

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    summary = {
        "sunday": 0, "weekday": 0, "feast": 0, "funeral": 0, "wedding": 0,
        "skipped_existing": 0, "flagged": 0, "unreadable": 0, "errors": [],
        "total_seen": 0,
    }

    # Year folders -> Sunday / weekday / feast
    for folder, cycle in YEAR_FOLDERS.items():
        fpath = os.path.join(root, folder)
        if not os.path.isdir(fpath):
            continue
        for filename in sorted(os.listdir(fpath)):
            if (filename.startswith(".") or filename.startswith("~$")
                    or not filename.lower().endswith(READABLE)):
                continue
            source_file = os.path.join(folder, filename)
            summary["total_seen"] += 1
            if _already_imported(db, source_file):
                summary["skipped_existing"] += 1
                continue
            try:
                fields = parse_sunday(filename, cycle)
                body, read_note = extract_text(os.path.join(fpath, filename))
                if read_note:
                    fields["import_note"] = " ".join(
                        p for p in (fields.get("import_note"), read_note) if p)
                    if not body:
                        summary["unreadable"] += 1
                _insert(db, fields, body, source_file)
                summary[fields["type"]] += 1
                if fields.get("import_note"):
                    summary["flagged"] += 1
            except Exception as e:  # never let one bad file stop the import
                summary["errors"].append(f"{source_file}: {e}")

    # Funeral folder -> funeral records
    fpath = os.path.join(root, FUNERAL_FOLDER)
    if os.path.isdir(fpath):
        for filename in sorted(os.listdir(fpath)):
            if (filename.startswith(".") or filename.startswith("~$")
                    or not filename.lower().endswith(READABLE)):
                continue
            source_file = os.path.join(FUNERAL_FOLDER, filename)
            summary["total_seen"] += 1
            if _already_imported(db, source_file):
                summary["skipped_existing"] += 1
                continue
            try:
                fields = parse_funeral(filename)
                body, read_note = extract_text(os.path.join(fpath, filename))
                if read_note:
                    fields["import_note"] = " ".join(
                        p for p in (fields.get("import_note"), read_note) if p)
                    if not body:
                        summary["unreadable"] += 1
                homily_id = _insert(db, fields, body, source_file)
                db.execute(
                    "INSERT INTO funeral_details (homily_id, deceased_name, "
                    "date_of_funeral) VALUES (?, ?, ?)",
                    (homily_id, fields.get("deceased_name"),
                     fields.get("date_of_funeral")))
                summary["funeral"] += 1
                if fields.get("import_note"):
                    summary["flagged"] += 1
            except Exception as e:
                summary["errors"].append(f"{source_file}: {e}")

    # Weddings folder -> wedding records (lighter occasional homilies)
    fpath = os.path.join(root, WEDDINGS_FOLDER)
    if os.path.isdir(fpath):
        for filename in sorted(os.listdir(fpath)):
            if (filename.startswith(".") or filename.startswith("~$")
                    or not filename.lower().endswith(READABLE)):
                continue
            source_file = os.path.join(WEDDINGS_FOLDER, filename)
            summary["total_seen"] += 1
            if _already_imported(db, source_file):
                summary["skipped_existing"] += 1
                continue
            try:
                fields = parse_wedding(filename)
                body, read_note = extract_text(os.path.join(fpath, filename))
                if read_note:
                    fields["import_note"] = " ".join(
                        p for p in (fields.get("import_note"), read_note) if p)
                    if not body:
                        summary["unreadable"] += 1
                homily_id = _insert(db, fields, body, source_file)
                if fields["type"] == "wedding":
                    db.execute(
                        "INSERT INTO occasion_details (homily_id, people) "
                        "VALUES (?, ?)", (homily_id, fields.get("people")))
                    summary["wedding"] += 1
                if fields.get("import_note"):
                    summary["flagged"] += 1
            except Exception as e:
                summary["errors"].append(f"{source_file}: {e}")

    db.commit()
    db.close()
    return summary


def format_summary(s):
    lines = [
        f"Looked at {s['total_seen']} files.",
        f"  Sunday: {s['sunday']}   Weekday: {s['weekday']}   "
        f"Feast/solemnity: {s['feast']}   Funeral: {s['funeral']}   "
        f"Wedding: {s['wedding']}",
        f"  Already imported, skipped: {s['skipped_existing']}",
        f"  Flagged for your review: {s['flagged']}",
        f"  Text could not be read (flagged): {s['unreadable']}",
    ]
    if s["errors"]:
        lines.append(f"  Errors: {len(s['errors'])}")
        for e in s["errors"][:10]:
            lines.append(f"    - {e}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Importing your existing homilies. This reads every file, so it can "
          "take a couple of minutes the first time...\n")
    result = run_import()
    print(format_summary(result))
    print("\nDone. Open the app to see your library.")
