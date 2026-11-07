"""
Homily Manager - load the official Sunday/feast readings into the app.

Reads data/lectionary_official.json (the Roman Catholic Lectionary for Mass,
1998 USA edition — the scripture references for every Sunday and principal feast
in Years A, B, and C) and fills the lectionary_readings table. The planner then
shows the assigned readings for each coming Sunday, and a homily started from the
planner begins with them.

The references are factual; the compiled tables they were taken from are by
Felix Just, S.J., Ph.D. (catholic-resources.org). Re-runnable.

    python load_official_lectionary.py
"""

import os
import json
import sqlite3

import lectionary

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "database", "homilies.db")
DATA_PATH = os.path.join(BASE_DIR, "data", "lectionary_official.json")


def load_official(db_path=None):
    db_path = db_path or os.environ.get("HOMILY_DB", DEFAULT_DB)
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    db = sqlite3.connect(db_path)
    # the official readings replace any earlier (homily-derived) table
    db.execute("DELETE FROM lectionary_readings")
    for e in data:
        db.execute(
            "INSERT OR REPLACE INTO lectionary_readings "
            "(signature, cycle_year, liturgical_day, season, first_reading, "
            " psalm, second_reading, gospel, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'official')",
            (e["signature"], e["cycle_year"], e.get("liturgical_day"), None,
             e.get("first_reading"), e.get("psalm"), e.get("second_reading"),
             e.get("gospel")))
    db.commit()
    db.close()
    return len(data)


ROLES = ("first_reading", "psalm", "second_reading", "gospel")


def apply_to_homilies(db_path=None):
    """Set every Sunday/feast homily's readings to the official assigned readings
    for its day and cycle, replacing whatever it had. Homilies whose day/cycle is
    not in the lectionary (or has no cycle) are left alone. Returns a summary."""
    db_path = db_path or os.environ.get("HOMILY_DB", DEFAULT_DB)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    homs = db.execute(
        "SELECT id, liturgical_day, season, cycle_year FROM homilies "
        "WHERE type IN ('sunday','feast') AND cycle_year IS NOT NULL").fetchall()
    summary = {"matched": 0, "no_match": 0}
    for h in homs:
        sig = lectionary.signature(h["season"], h["liturgical_day"] or "")
        lect = db.execute(
            "SELECT * FROM lectionary_readings WHERE signature = ? AND cycle_year = ?",
            (sig, h["cycle_year"])).fetchone() if sig else None
        if not lect or not any(lect[r] for r in ROLES):
            summary["no_match"] += 1
            continue
        db.execute("DELETE FROM readings WHERE homily_id = ?", (h["id"],))
        for role in ROLES:
            if lect[role]:
                db.execute("INSERT INTO readings (homily_id, role, citation) "
                           "VALUES (?, ?, ?)", (h["id"], role, lect[role]))
        summary["matched"] += 1
    db.commit()
    db.close()
    return summary


if __name__ == "__main__":
    n = load_official()
    print(f"Loaded {n} official Sunday/feast readings (Years A, B, C).")
    s = apply_to_homilies()
    print(f"Applied official readings to {s['matched']} homilies "
          f"({s['no_match']} had no match and were left as they were).")
