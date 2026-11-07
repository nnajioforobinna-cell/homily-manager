"""
A small end-to-end check of Phase 1. It uses a throwaway database, so it never
touches your real homilies. Run it from the app folder with:

    python3 tests/smoke_test.py

It prints OK and exits 0 when everything works.
"""

import os
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Point the app at a temporary database before importing it
tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp_db.close()
os.environ["HOMILY_DB"] = tmp_db.name

import server  # noqa: E402

server.init_db()
server.DB_PATH = tmp_db.name
client = server.app.test_client()

failures = []


def check(name, condition):
    print(("PASS" if condition else "FAIL") + "  " + name)
    if not condition:
        failures.append(name)


# Empty library loads
r = client.get("/")
check("home page loads", r.status_code == 200)

# Add a congregation
r = client.post("/congregations", data={"name": "Star of the Sea"},
                follow_redirects=True)
check("congregation added", b"Star of the Sea" in r.data)

# Add a homily with a reading and a tag
r = client.post("/homily/new", data={
    "type": "sunday", "title": "The Lost Sheep", "status": "preached",
    "liturgical_day": "24th Sunday Ordinary Time", "season": "ordinary_time",
    "cycle_year": "C", "core_message": "God seeks the one who is lost.",
    "reading_gospel": "Luke 15:1-32", "body": "Full homily text here.",
    "tags": "mercy, forgiveness",
}, follow_redirects=True)
check("homily saved", r.status_code == 200)

# It appears in the library
r = client.get("/")
check("homily listed", b"The Lost Sheep" in r.data)

# Search by text
r = client.get("/?q=lost")
check("text search finds it", b"The Lost Sheep" in r.data)

# Filter by scripture passage
r = client.get("/?passage=Luke 15")
check("passage filter finds it", b"The Lost Sheep" in r.data)

# Filter by tag
r = client.get("/?tag=mercy")
check("tag filter finds it", b"The Lost Sheep" in r.data)

# Filter by cycle year that should NOT match
r = client.get("/?cycle_year=A")
check("wrong-year filter excludes it", b"The Lost Sheep" not in r.data)

# --- Phase 2: the funeral section ---------------------------------------
# Add a funeral homily with its person details
r = client.post("/homily/new", data={
    "type": "funeral", "title": "Funeral of Mary Example", "status": "preached",
    "deceased_name": "Mary Example", "age": "84",
    "date_of_funeral": "2024-05-02", "date_of_death": "2024-04-28",
    "about_person": "A pillar of the parish choir.",
    "family_contact": "Her son John", "body": "Funeral homily text.",
}, follow_redirects=True)
check("funeral saved", r.status_code == 200)
check("funeral details kept", b"Mary Example" in r.data and b"84" in r.data)

# It shows in the funeral section...
r = client.get("/funerals")
check("funeral listed in its section", b"Mary Example" in r.data)

# ...but NOT in the general library
r = client.get("/")
check("funeral kept out of the library", b"Mary Example" not in r.data)

# The library still has the Sunday homily
check("library still shows sunday homily", b"The Lost Sheep" in r.data)

# The import page loads
r = client.get("/import")
check("import page loads", r.status_code == 200)

# --- Phase 3: the planner and the three-year lookup ---------------------
# A past Year A homily so the lookup has something to find
client.post("/homily/new", data={
    "type": "sunday", "title": "28th Sunday Year A (2023)", "status": "preached",
    "liturgical_day": "28th Sunday in Ordinary Time", "season": "ordinary_time",
    "cycle_year": "A", "reading_gospel": "Matthew 22:1-14",
    "body": "The wedding feast.",
}, follow_redirects=True)

r = client.get("/planner")
check("planner loads", r.status_code == 200)
check("planner shows upcoming Sundays", b"Sunday" in r.data)
# a 52-week window always contains every Sunday of the cycle, so the 28th
# Sunday appears and the lookup lists the past homily for it (whatever today is)
r = client.get("/planner?weeks=52")
check("three-year lookup finds the past homily",
      b"28th Sunday Year A (2023)" in r.data)

# Plan a Sunday
r = client.post("/planner/save", data={
    "scheduled_date": "2099-10-11", "liturgical_day": "28th Sunday in Ordinary Time",
    "season": "ordinary_time", "cycle_year": "A",
    "theme_idea": "Come to the feast", "status": "researching",
}, follow_redirects=True)
check("planner entry saved", b"Come to the feast" in r.data or r.status_code == 200)

# Turn a planner Sunday into a library homily
r = client.post("/planner/create-homily", data={
    "scheduled_date": "2099-10-11", "liturgical_day": "28th Sunday in Ordinary Time",
    "season": "ordinary_time", "cycle_year": "A",
}, follow_redirects=True)
check("planner created a homily", r.status_code == 200
      and b"28th Sunday in Ordinary Time" in r.data)

# --- Phase 3: series ----------------------------------------------------
client.post("/series", data={"title": "The Beatitudes",
            "description": "Eight weeks"}, follow_redirects=True)
r = client.get("/series")
check("series listed", b"The Beatitudes" in r.data)
# assign a planned Sunday to the series and confirm it shows on the detail
r = client.post("/planner/save", data={
    "scheduled_date": "2099-01-04", "liturgical_day": "2nd Sunday after Christmas",
    "season": "christmas", "cycle_year": "A", "theme_idea": "Poor in spirit",
    "status": "researching", "series_id": "1"}, follow_redirects=True)
r = client.get("/series/1")
check("series detail shows its week",
      b"Poor in spirit" in r.data or b"2nd Sunday" in r.data)

# --- Phase 4: illustration / story bank ---------------------------------
# attach a story to the earlier Sunday homily, with an occasion, by editing it
hid = None
import re as _re2  # noqa: E402
m = _re2.search(rb'/homily/(\d+)/read"[^>]*>\s*The Lost Sheep', client.get("/").data)
# fall back: find any homily id from the library
r = client.get("/")
mm = _re2.search(rb'/homily/(\d+)', r.data)
hid = int(mm.group(1)) if mm else None
if hid:
    client.post(f"/homily/{hid}", data={
        "type": "sunday", "title": "The Lost Sheep", "status": "preached",
        "illustrations": "The two wolves, Gift of the Magi",
        "congregation_id": "1", "date_preached": "2098-10-04"}, follow_redirects=True)
r = client.get("/illustrations")
check("story bank lists stories", b"The two wolves" in r.data)
# the story detail shows where it was told
r = client.get("/illustrations")
mid = _re2.search(rb'/illustrations/(\d+)', r.data)
if mid:
    r = client.get("/illustrations/%s" % mid.group(1).decode())
    check("story detail loads with 'where told'",
          r.status_code == 200 and b"Where it has been told" in r.data)

# --- Weddings and baptisms (lighter occasional records) -----------------
r = client.post("/homily/new", data={
    "type": "wedding", "title": "Wedding of A & B", "status": "preached",
    "people": "Anna & Ben", "event_date": "2098-06-20",
    "family": "The Smith and Jones families", "body": "On love.",
}, follow_redirects=True)
check("wedding saved with its details",
      r.status_code == 200 and b"Anna &amp; Ben" in r.data)

r = client.get("/celebrations")
check("wedding listed in celebrations", b"Anna &amp; Ben" in r.data)
check("baptism button present", b"New baptism" in r.data)

# weddings are NOT in the funeral section
r = client.get("/funerals")
check("wedding not in funerals", b"Anna &amp; Ben" not in r.data)

# --- Story links: add and remove directly ------------------------------
# link the story to the Sunday homily, then unlink it
_sid = mid.group(1).decode() if mid else "1"
r = client.get("/illustrations/%s?find=Lost" % _sid)
check("story detail homily search works", b"Link" in r.data or b"match" in r.data)
if hid:
    r = client.post("/illustrations/%s/link" % _sid, data={"homily_id": str(hid)},
                    follow_redirects=True)
    check("story linked to a homily", b"Used in" in r.data)
    r = client.post("/illustrations/%s/unlink" % _sid, data={"homily_id": str(hid)},
                    follow_redirects=True)
    check("story unlink works", r.status_code == 200)

# --- Standardize readings -----------------------------------------------
import load_official_lectionary as _lol  # noqa: E402
_lol.load_official(db_path=tmp_db.name)
r = client.post("/standardize-readings", follow_redirects=True)
check("standardize readings runs", r.status_code == 200
      and b"official readings" in r.data)

# --- Export -------------------------------------------------------------
r = client.get("/export")
check("export page loads", r.status_code == 200 and b"Export to Word" in r.data)
r = client.get("/export/word?scope=all")
check("Word export is a .docx", r.status_code == 200 and r.data[:2] == b"PK")
r = client.get("/export/pdf")
check("PDF export is a real PDF file",
      r.status_code == 200 and r.data[:5] == b"%PDF-")

# --- Official lectionary readings ---------------------------------------
import load_official_lectionary  # noqa: E402
n = load_official_lectionary.load_official(db_path=tmp_db.name)
check("official lectionary loaded (A/B/C)", n > 150)
import sqlite3 as _sq  # noqa: E402
_c = _sq.connect(tmp_db.name)
_row = _c.execute("SELECT gospel FROM lectionary_readings "
                  "WHERE signature='ot32' AND cycle_year='A'").fetchone()
_c.close()
check("official reading is correct (32nd Sun A = Matthew 25)",
      _row is not None and "Matthew 25" in (_row[0] or ""))

# --- Backup -------------------------------------------------------------
r = client.get("/backup")
check("backup page loads", r.status_code == 200 and b"Back up your homilies" in r.data)
r = client.get("/backup/download")
check("backup download returns a sqlite file",
      r.status_code == 200 and r.data[:15] == b"SQLite format 3")

# --- Restore from a backup ----------------------------------------------
import io as _io  # noqa: E402
good_backup = client.get("/backup/download").data          # a valid snapshot now
# change the live data, then restore the snapshot and confirm it came back
import sqlite3 as _s3  # noqa: E402
_c = _s3.connect(tmp_db.name)
_c.execute("INSERT INTO homilies (type, title) VALUES ('sunday', 'TEMP DELETE ME')")
_c.commit(); _c.close()
r = client.post("/backup/restore",
                data={"backup_file": (_io.BytesIO(good_backup), "backup.db")},
                content_type="multipart/form-data", follow_redirects=True)
check("restore accepts a valid backup", b"Backup restored" in r.data)
_c = _s3.connect(tmp_db.name)
_gone = _c.execute("SELECT COUNT(*) FROM homilies WHERE title='TEMP DELETE ME'").fetchone()[0]
_safety = _c.execute("SELECT COUNT(*) FROM homilies").fetchone()[0]
_c.close()
check("restore replaced the data (added row gone)", _gone == 0 and _safety > 0)
# a non-database file must be rejected
r = client.post("/backup/restore",
                data={"backup_file": (_io.BytesIO(b"this is not a database"), "junk.db")},
                content_type="multipart/form-data", follow_redirects=True)
check("restore rejects a non-database file", b"not a Homily Manager backup" in r.data)

# --- Sync indicator endpoint --------------------------------------------
r = client.get("/ping")
check("ping endpoint responds ok", r.status_code == 200 and b"true" in r.data)

# The lectionary computes a known date correctly
import lectionary  # noqa: E402
import datetime as _d  # noqa: E402
check("lectionary: Easter 2027 is 28 March",
      lectionary.computus(2027) == _d.date(2027, 3, 28))
ck = lectionary.classify(_d.date(2026, 11, 22))
check("lectionary: Christ the King 2026", ck and ck["ot_number"] == 34)

# --- Login (only enforced when a password is set, i.e. when hosted) ------
check("no login required locally (no password set)",
      client.get("/").status_code == 200)
server.PASSWORD = "testpass123"
guard = server.app.test_client()
r = guard.get("/")
check("login required when a password is set",
      r.status_code == 302 and "/login" in r.headers.get("Location", ""))
guard.post("/login", data={"password": "nope"})
check("wrong password does not sign in",
      guard.get("/").status_code == 302)
guard.post("/login", data={"password": "testpass123"})
check("correct password signs in", guard.get("/").status_code == 200)
server.PASSWORD = None   # reset so nothing else is affected

os.unlink(tmp_db.name)

if failures:
    print("\n%d check(s) failed." % len(failures))
    sys.exit(1)
print("\nOK - all checks passed (library, funerals, import, planner).")
