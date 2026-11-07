"""
Homily Manager - compile the Sunday readings table from your own homilies.

You have preached two full A/B/C cycles (2020-2026), and each homily's readings
were already read out of its text. This gathers them into one canonical table of
the readings for each Sunday and feast, by cycle year, taking the reading that
recurs across your homilies for that day (and the fullest citation of it). The
planner then shows the assigned readings for a coming Sunday, and a new homily
started from the planner begins with them already filled in.

The readings come from your own homilies, so they are as right as what you
preached; correct any on the homily itself. Re-runnable.

Run it on its own:
    python build_lectionary.py
"""

import os
import re
import sqlite3
import collections

import lectionary

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "database", "homilies.db")
ROLES = ["first_reading", "psalm", "second_reading", "gospel"]


def _consensus(citations):
    """Pick the reading that recurs most across the homilies for a day; ties go
    to the fullest citation (the one covering the widest verse range)."""
    if not citations:
        return None
    # group by book + chapter so "Mark 4:35-41" and "Mark 4:35" count together
    def bookchap(c):
        m = re.match(r"^(.*?\d+)", c)
        return (m.group(1) if m else c).lower()
    groups = collections.defaultdict(list)
    for c in citations:
        groups[bookchap(c)].append(c)
    best_group = max(groups.values(),
                     key=lambda g: (len(g), max(len(x) for x in g)))
    # within the winning book+chapter, the fullest (longest) citation
    return max(best_group, key=len)


def build_from_homilies(db_path=None):
    db_path = db_path or os.environ.get("HOMILY_DB", DEFAULT_DB)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    buckets = collections.defaultdict(lambda: collections.defaultdict(list))
    labels = {}
    rows = db.execute(
        "SELECT id, liturgical_day, season, cycle_year FROM homilies "
        "WHERE type IN ('sunday','feast') AND cycle_year IS NOT NULL "
        "AND status != 'archived'").fetchall()
    for r in rows:
        sig = lectionary.signature(r["season"], r["liturgical_day"] or "")
        if not sig:
            continue
        key = (sig, r["cycle_year"])
        labels.setdefault(key, (r["liturgical_day"], r["season"]))
        for rd in db.execute(
                "SELECT role, citation FROM readings WHERE homily_id = ?",
                (r["id"],)).fetchall():
            if rd["role"] in ROLES:
                buckets[key][rd["role"]].append(rd["citation"])

    summary = {"days": 0, "with_gospel": 0, "roles": 0}
    for (sig, cyc), roles in buckets.items():
        vals = {role: _consensus(roles.get(role)) for role in ROLES}
        day, season = labels[(sig, cyc)]
        db.execute(
            "INSERT INTO lectionary_readings "
            "(signature, cycle_year, liturgical_day, season, "
            " first_reading, psalm, second_reading, gospel, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'homilies') "
            "ON CONFLICT(signature, cycle_year) DO UPDATE SET "
            "liturgical_day=excluded.liturgical_day, season=excluded.season, "
            "first_reading=excluded.first_reading, psalm=excluded.psalm, "
            "second_reading=excluded.second_reading, gospel=excluded.gospel, "
            "source='homilies'",
            (sig, cyc, day, season, vals["first_reading"], vals["psalm"],
             vals["second_reading"], vals["gospel"]))
        summary["days"] += 1
        if vals["gospel"]:
            summary["with_gospel"] += 1
        summary["roles"] += sum(1 for v in vals.values() if v)

    db.commit()
    db.close()
    return summary


if __name__ == "__main__":
    s = build_from_homilies()
    print(f"Built readings for {s['days']} day/cycle combinations "
          f"({s['with_gospel']} with a gospel, {s['roles']} readings in all).")
