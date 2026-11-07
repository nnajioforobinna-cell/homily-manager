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


if __name__ == "__main__":
    n = load_official()
    print(f"Loaded {n} official Sunday/feast readings (Years A, B, C).")
