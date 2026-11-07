"""
Homily Manager - gather the stories and illustrations out of the homilies.

Many homilies carry a story, often marked in the text ("Story:", "Intro Story:",
"There is a story about...", "Once upon a time..."). This reads every homily,
pulls those stories out, gathers the same story told in more than one homily into
a single record, and fills the illustration and story bank (specification section
8), each story linked to every homily that used it.

A best-effort first pass: it finds the clearly-marked stories, not every passing
illustration, and the priest can edit, merge, or remove any in the bank.

Run it on its own:
    python extract_stories.py
"""

import os
import re
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "database", "homilies.db")

# A labelled story at the start of a paragraph: "Story: ...", "Intro Story: ...",
# "CONCLUDING STORY - ...", "Illustration: ...".
LABEL_RE = re.compile(
    r"^\s*(?:[•‣●·*\-]\s*)?"
    r"(?:intro(?:ductory)?|introduction|concluding|opening|closing|final|second|another)?\s*"
    r"(?:story|illustration|anecdote|parable|example)\s*[:\-]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE)

# A story that begins mid-paragraph with a tell-tale phrase; take it to the end
# of that paragraph (one line, since paragraphs are newline-separated).
INLINE_RE = re.compile(
    r"((?:there (?:is|was) (?:a|an old|this|a certain) (?:story|tale|legend|anecdote|parable)"
    r"|a (?:story|tale) is told"
    r"|once upon a time"
    r"|once there (?:was|lived))\b[^\n]{20,})",
    re.IGNORECASE)

# Lines that are only a heading, not a story worth keeping.
MIN_LEN = 60
MAX_LEN = 1600


def _clean(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    # drop leading ellipses / dashes / bullets left from the paragraph
    s = re.sub(r'^[\s.…\-–•*:;,]+', "", s)
    return s.strip()


def make_title(content):
    """A short title for a story: its first sentence, or its first few words."""
    s = _clean(content)
    m = re.match(r"(.{12,72}?[.!?])(?:\s|$)", s)
    title = m.group(1) if m else " ".join(s.split()[:9])
    title = title.strip().rstrip(".!?,;:— ")
    if len(title) > 72:
        title = title[:69].rsplit(" ", 1)[0] + "…"
    return title or "Story"


def extract_stories(body):
    """Return a list of {title, content} for the stories found in one homily."""
    if not body:
        return []
    found, seen = [], set()
    for m in LABEL_RE.finditer(body):
        content = _clean(m.group(1))[:MAX_LEN]
        if len(content) >= MIN_LEN:
            key = content[:80].lower()
            if key not in seen:
                seen.add(key)
                found.append({"title": make_title(content), "content": content})
    for m in INLINE_RE.finditer(body):
        content = _clean(m.group(1))[:MAX_LEN]
        if len(content) >= MIN_LEN:
            key = content[:80].lower()
            if key not in seen:
                seen.add(key)
                found.append({"title": make_title(content), "content": content})
    return found


def _dedup_key(content):
    # strip to letters/digits first, then take a prefix, so punctuation and
    # leading ellipses never shift the key
    return re.sub(r"[^a-z0-9]", "", (content or "").lower())[:80]


def aggregate(db_path=None):
    """Fill the illustration bank from the homilies. Same story in several
    homilies becomes one record linked to each. Returns a summary dict."""
    db_path = db_path or os.environ.get("HOMILY_DB", DEFAULT_DB)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    # existing auto-gathered stories, so re-running links rather than duplicates
    existing = {}
    for r in db.execute("SELECT id, content FROM illustrations "
                        "WHERE content IS NOT NULL").fetchall():
        existing[_dedup_key(r["content"])] = r["id"]

    rows = db.execute(
        "SELECT id, body FROM homilies WHERE body IS NOT NULL").fetchall()
    summary = {"homilies_scanned": len(rows), "stories_found": 0,
               "new_stories": 0, "links": 0, "homilies_with_story": 0}
    bank = {}   # dedup_key -> {"id" or "title"/"content", "homilies": set}

    for r in rows:
        stories = extract_stories(r["body"])
        if stories:
            summary["homilies_with_story"] += 1
        for st in stories:
            summary["stories_found"] += 1
            key = _dedup_key(st["content"])
            if key not in bank:
                bank[key] = {"title": st["title"], "content": st["content"],
                             "homilies": set(), "existing_id": existing.get(key)}
            bank[key]["homilies"].add(r["id"])

    for key, rec in bank.items():
        if rec["existing_id"]:
            ill_id = rec["existing_id"]
            # refresh the tidied title/content on a re-run
            db.execute("UPDATE illustrations SET title=?, content=? WHERE id=?",
                       (rec["title"], rec["content"], ill_id))
        else:
            ill_id = db.execute(
                "INSERT INTO illustrations (title, content) VALUES (?, ?)",
                (rec["title"], rec["content"])).lastrowid
            summary["new_stories"] += 1
        for hid in rec["homilies"]:
            cur = db.execute(
                "INSERT OR IGNORE INTO homily_illustrations "
                "(homily_id, illustration_id) VALUES (?, ?)", (hid, ill_id))
            summary["links"] += cur.rowcount

    db.commit()
    db.close()
    return summary


if __name__ == "__main__":
    print("Gathering the stories out of your homilies...\n")
    s = aggregate()
    print(f"Scanned {s['homilies_scanned']} homilies; "
          f"{s['homilies_with_story']} had a marked story.")
    print(f"  Stories found: {s['stories_found']}")
    print(f"  Distinct stories added to the bank: {s['new_stories']}")
    print(f"  Links made (story used in a homily): {s['links']}")
    print("\nDone. Open the Stories page to see them.")
