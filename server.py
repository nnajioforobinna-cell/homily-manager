"""
Homily Manager - local web app (Phase 1).

A single-user application you run on your own mac. It opens in your web browser
but stays entirely on your computer: no account, no login, nothing on the
internet. The whole database is one file, database/homilies.db.

Run it:
    python3 server.py
Then open http://127.0.0.1:5050 in your browser.
"""

import os
import re
import io
import html
import sqlite3
import datetime
import tempfile
from flask import (
    Flask, g, render_template, request, redirect, url_for, flash, abort,
    send_file
)
from markupsafe import Markup
import lectionary

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
DEFAULT_DB = os.path.join(BASE_DIR, "database", "homilies.db")
DB_PATH = os.environ.get("HOMILY_DB", DEFAULT_DB)
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
# Port 5000 is taken by macOS (AirPlay Receiver / Control Center) on recent
# versions, so the app uses 5050 by default. Override with HOMILY_PORT.
PORT = int(os.environ.get("HOMILY_PORT", "5050"))

app = Flask(__name__)
app.secret_key = "local-only-not-a-secret"  # only used for flash messages


def format_body(text):
    """Turn a homily's plain text into readable HTML paragraphs. The imported
    text uses a single newline (and the odd Unicode line separator) between
    paragraphs, which reads as one cramped block; this gives each its own
    paragraph, and sets bulleted lines as a list."""
    if not text:
        return Markup("")
    t = (text.replace(" ", "\n").replace(" ", "\n\n")
             .replace("\r\n", "\n").replace("\r", "\n"))
    blocks = [b.strip() for b in re.split(r"\n+", t)]
    out, bullets = [], []

    def flush_bullets():
        if bullets:
            items = "".join(f"<li>{html.escape(b)}</li>" for b in bullets)
            out.append(f"<ul>{items}</ul>")
            bullets.clear()

    for b in blocks:
        if not b:
            continue
        m = re.match(r"^\s*(?:[•‣●·*]|[-–])\s+(.*)", b)
        if m:
            bullets.append(m.group(1))
        else:
            flush_bullets()
            out.append(f"<p>{html.escape(b)}</p>")
    flush_bullets()
    return Markup("\n".join(out))


app.jinja_env.filters["format_body"] = format_body

# Fixed lists used by the forms and filters
HOMILY_TYPES = [
    ("sunday", "Sunday"), ("weekday", "Weekday"), ("funeral", "Funeral"),
    ("wedding", "Wedding"), ("baptism", "Baptism"), ("feast", "Feast or solemnity"),
    ("other", "Other"),
]
# The library shows everything except funerals, which live in their own section
# (specification section 6: kept apart from the general library).
LIBRARY_TYPES = [t for t in HOMILY_TYPES if t[0] != "funeral"]
SEASONS = [
    ("advent", "Advent"), ("christmas", "Christmas"), ("lent", "Lent"),
    ("easter", "Easter"), ("ordinary_time", "Ordinary Time"), ("other", "Other"),
]
CYCLE_YEARS = [("A", "A"), ("B", "B"), ("C", "C"), ("I", "I"), ("II", "II")]
STATUSES = [
    ("draft", "Draft"), ("ready", "Ready"), ("preached", "Preached"),
    ("archived", "Archived"),
]
READING_ROLES = [
    ("first_reading", "First reading"), ("psalm", "Responsorial psalm"),
    ("second_reading", "Second reading"), ("gospel", "Gospel"), ("other", "Other"),
]
PLANNER_STATUSES = [
    ("not_started", "Not started"), ("researching", "Researching"),
    ("drafted", "Drafted"), ("ready", "Ready"),
]


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the database file from the schema if it does not exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    migrate(conn)
    conn.commit()
    conn.close()


def migrate(conn):
    """Add columns introduced after the first version, for databases that were
    created before them. Safe to run every start."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(homilies)").fetchall()}
    if "source_file" not in cols:
        conn.execute("ALTER TABLE homilies ADD COLUMN source_file TEXT")
    if "import_note" not in cols:
        conn.execute("ALTER TABLE homilies ADD COLUMN import_note TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_homilies_source "
        "ON homilies(source_file) WHERE source_file IS NOT NULL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS occasion_details ("
        "homily_id INTEGER PRIMARY KEY REFERENCES homilies(id) ON DELETE CASCADE, "
        "people TEXT, family TEXT, event_date TEXT, note TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS lectionary_readings ("
        "signature TEXT NOT NULL, cycle_year TEXT NOT NULL, liturgical_day TEXT, "
        "season TEXT, first_reading TEXT, psalm TEXT, second_reading TEXT, "
        "gospel TEXT, source TEXT, PRIMARY KEY (signature, cycle_year))")


def tags_for(db, homily_id):
    rows = db.execute(
        "SELECT t.name FROM tags t JOIN homily_tags ht ON ht.tag_id = t.id "
        "WHERE ht.homily_id = ? ORDER BY t.name", (homily_id,)
    ).fetchall()
    return [r["name"] for r in rows]


def save_tags(db, homily_id, tag_text):
    """Replace a homily's tags from a comma-separated string."""
    db.execute("DELETE FROM homily_tags WHERE homily_id = ?", (homily_id,))
    names = [t.strip() for t in (tag_text or "").split(",") if t.strip()]
    for name in names:
        row = db.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        if row:
            tag_id = row["id"]
        else:
            cur = db.execute("INSERT INTO tags (name) VALUES (?)", (name,))
            tag_id = cur.lastrowid
        db.execute(
            "INSERT OR IGNORE INTO homily_tags (homily_id, tag_id) VALUES (?, ?)",
            (homily_id, tag_id),
        )


def illustrations_for(db, homily_id):
    return db.execute(
        "SELECT i.* FROM illustrations i "
        "JOIN homily_illustrations hi ON hi.illustration_id = i.id "
        "WHERE hi.homily_id = ? ORDER BY i.title", (homily_id,)).fetchall()


def save_illustrations(db, homily_id, text):
    """Link a homily to illustrations named in a comma-separated string, making
    a stub illustration for any that is new (the story and source are filled in
    later in the illustration bank)."""
    db.execute("DELETE FROM homily_illustrations WHERE homily_id = ?", (homily_id,))
    for name in [t.strip() for t in (text or "").split(",") if t.strip()]:
        row = db.execute(
            "SELECT id FROM illustrations WHERE title = ? COLLATE NOCASE", (name,)
        ).fetchone()
        ill_id = row["id"] if row else db.execute(
            "INSERT INTO illustrations (title) VALUES (?)", (name,)).lastrowid
        db.execute("INSERT OR IGNORE INTO homily_illustrations "
                   "(homily_id, illustration_id) VALUES (?, ?)", (homily_id, ill_id))


def save_readings(db, homily_id, form):
    """Replace a homily's readings from the four standard form fields."""
    db.execute("DELETE FROM readings WHERE homily_id = ?", (homily_id,))
    for role, _label in READING_ROLES:
        citation = (form.get("reading_" + role) or "").strip()
        if citation:
            db.execute(
                "INSERT INTO readings (homily_id, role, citation) VALUES (?, ?, ?)",
                (homily_id, role, citation),
            )


def readings_for(db, homily_id):
    rows = db.execute(
        "SELECT role, citation FROM readings WHERE homily_id = ?", (homily_id,)
    ).fetchall()
    return {r["role"]: r["citation"] for r in rows}


def save_occasion(db, homily_id, form):
    """Keep a single 'preached at' occasion in step with the form (Phase 1)."""
    cong = form.get("congregation_id") or None
    date = (form.get("date_preached") or "").strip() or None
    notes = (form.get("occasion_notes") or "").strip() or None
    db.execute("DELETE FROM homily_occasions WHERE homily_id = ?", (homily_id,))
    if cong or date or notes:
        db.execute(
            "INSERT INTO homily_occasions (homily_id, congregation_id, date_preached, notes) "
            "VALUES (?, ?, ?, ?)",
            (homily_id, cong, date, notes),
        )


def occasion_for(db, homily_id):
    return db.execute(
        "SELECT * FROM homily_occasions WHERE homily_id = ? LIMIT 1", (homily_id,)
    ).fetchone()


def funeral_for(db, homily_id):
    return db.execute(
        "SELECT * FROM funeral_details WHERE homily_id = ?", (homily_id,)
    ).fetchone()


# Weddings and baptisms: the lighter occasional records (specification 6)
OCCASION_TYPES = ("wedding", "baptism")


def celebration_for(db, homily_id):
    return db.execute(
        "SELECT * FROM occasion_details WHERE homily_id = ?", (homily_id,)
    ).fetchone()


def save_celebration(db, homily_id, form):
    people = (form.get("people") or "").strip() or None
    family = (form.get("family") or "").strip() or None
    event_date = (form.get("event_date") or "").strip() or None
    note = (form.get("celebration_note") or "").strip() or None
    db.execute("DELETE FROM occasion_details WHERE homily_id = ?", (homily_id,))
    if any([people, family, event_date, note]):
        db.execute(
            "INSERT INTO occasion_details (homily_id, people, family, event_date, note) "
            "VALUES (?, ?, ?, ?, ?)", (homily_id, people, family, event_date, note))


def save_funeral(db, homily_id, form):
    """Keep the funeral detail row in step with the form (specification 6)."""
    deceased = (form.get("deceased_name") or "").strip() or None
    dod = (form.get("date_of_death") or "").strip() or None
    dof = (form.get("date_of_funeral") or "").strip() or None
    age_raw = (form.get("age") or "").strip()
    age = int(age_raw) if age_raw.isdigit() else None
    about = (form.get("about_person") or "").strip() or None
    family = (form.get("family_contact") or "").strip() or None
    db.execute("DELETE FROM funeral_details WHERE homily_id = ?", (homily_id,))
    if any([deceased, dod, dof, age, about, family]):
        db.execute(
            "INSERT INTO funeral_details (homily_id, deceased_name, date_of_death, "
            "date_of_funeral, age, about_person, family_contact) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (homily_id, deceased, dod, dof, age, about, family),
        )


# --------------------------------------------------------------------------
# The library: list with search and filters
# --------------------------------------------------------------------------
@app.route("/")
def index():
    db = get_db()
    f = request.args
    # Funerals are kept in their own section, out of the general library.
    clauses, params = ["h.type != 'funeral'"], []

    if f.get("q", "").strip():
        like = f"%{f['q'].strip()}%"
        clauses.append("(h.title LIKE ? OR h.body LIKE ? OR h.core_message LIKE ?)")
        params += [like, like, like]
    if f.get("type"):
        clauses.append("h.type = ?"); params.append(f["type"])
    if f.get("season"):
        clauses.append("h.season = ?"); params.append(f["season"])
    if f.get("cycle_year"):
        clauses.append("h.cycle_year = ?"); params.append(f["cycle_year"])
    if f.get("liturgical_day", "").strip():
        clauses.append("h.liturgical_day LIKE ?")
        params.append(f"%{f['liturgical_day'].strip()}%")
    if f.get("passage", "").strip():
        clauses.append(
            "EXISTS (SELECT 1 FROM readings r WHERE r.homily_id = h.id "
            "AND r.citation LIKE ?)")
        params.append(f"%{f['passage'].strip()}%")
    if f.get("tag", "").strip():
        clauses.append(
            "EXISTS (SELECT 1 FROM homily_tags ht JOIN tags t ON t.id = ht.tag_id "
            "WHERE ht.homily_id = h.id AND t.name = ?)")
        params.append(f["tag"].strip())
    if f.get("congregation_id"):
        clauses.append(
            "EXISTS (SELECT 1 FROM homily_occasions o WHERE o.homily_id = h.id "
            "AND o.congregation_id = ?)")
        params.append(f["congregation_id"])
    if f.get("review") == "1":
        clauses.append("h.import_note IS NOT NULL")
    # Archived homilies (e.g. superseded old copies) are hidden unless asked for.
    if f.get("show_archived") != "1":
        clauses.append("h.status != 'archived'")

    sql = "SELECT h.* FROM homilies h"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY h.updated_at DESC"

    rows = db.execute(sql, params).fetchall()
    homilies = []
    for r in rows:
        d = dict(r)
        d["tags"] = tags_for(db, r["id"])
        homilies.append(d)

    congregations = db.execute(
        "SELECT * FROM congregations ORDER BY name").fetchall()
    all_tags = db.execute("SELECT name FROM tags ORDER BY name").fetchall()
    review_total = db.execute(
        "SELECT COUNT(*) FROM homilies WHERE type != 'funeral' "
        "AND import_note IS NOT NULL AND status != 'archived'").fetchone()[0]
    archived_total = db.execute(
        "SELECT COUNT(*) FROM homilies WHERE type != 'funeral' "
        "AND status = 'archived'").fetchone()[0]

    return render_template(
        "index.html", homilies=homilies, congregations=congregations,
        all_tags=[t["name"] for t in all_tags], filters=f,
        types=LIBRARY_TYPES, seasons=SEASONS, cycle_years=CYCLE_YEARS,
        total=len(homilies), review_total=review_total,
        archived_total=archived_total,
    )


# --------------------------------------------------------------------------
# Add / edit / delete a homily
# --------------------------------------------------------------------------
@app.route("/homily/new", methods=["GET", "POST"])
def homily_new():
    db = get_db()
    if request.method == "POST":
        homily_id = _save_homily(db, None, request.form)
        db.commit()
        flash("Homily saved.")
        return redirect(url_for("homily_edit", homily_id=homily_id))
    congregations = db.execute(
        "SELECT * FROM congregations ORDER BY name").fetchall()
    return render_template(
        "homily_form.html", homily=None, readings={}, occasion=None, tags="",
        illustrations="", funeral=None, celebration=None,
        default_type=request.args.get("type"),
        congregations=congregations, types=HOMILY_TYPES, seasons=SEASONS,
        cycle_years=CYCLE_YEARS, statuses=STATUSES, roles=READING_ROLES,
    )


@app.route("/homily/<int:homily_id>", methods=["GET", "POST"])
def homily_edit(homily_id):
    db = get_db()
    homily = db.execute(
        "SELECT * FROM homilies WHERE id = ?", (homily_id,)).fetchone()
    if homily is None:
        abort(404)
    if request.method == "POST":
        _save_homily(db, homily_id, request.form)
        db.commit()
        flash("Changes saved.")
        return redirect(url_for("homily_edit", homily_id=homily_id))
    congregations = db.execute(
        "SELECT * FROM congregations ORDER BY name").fetchall()
    return render_template(
        "homily_form.html", homily=homily, readings=readings_for(db, homily_id),
        occasion=occasion_for(db, homily_id), funeral=funeral_for(db, homily_id),
        celebration=celebration_for(db, homily_id), default_type=None,
        illustrations=", ".join(i["title"] for i in illustrations_for(db, homily_id)),
        tags=", ".join(tags_for(db, homily_id)), congregations=congregations,
        types=HOMILY_TYPES, seasons=SEASONS, cycle_years=CYCLE_YEARS,
        statuses=STATUSES, roles=READING_ROLES,
    )


@app.route("/homily/<int:homily_id>/read")
def homily_read(homily_id):
    db = get_db()
    homily = db.execute(
        "SELECT * FROM homilies WHERE id = ?", (homily_id,)).fetchone()
    if homily is None:
        abort(404)
    occasion = occasion_for(db, homily_id)
    cong = None
    if occasion and occasion["congregation_id"]:
        cong = db.execute("SELECT name FROM congregations WHERE id = ?",
                          (occasion["congregation_id"],)).fetchone()
    return render_template(
        "homily_read.html", homily=homily,
        readings=readings_for(db, homily_id), tags=tags_for(db, homily_id),
        illustrations=illustrations_for(db, homily_id),
        funeral=funeral_for(db, homily_id),
        celebration=celebration_for(db, homily_id),
        occasion=occasion, congregation=cong, roles=READING_ROLES,
    )


@app.route("/homily/<int:homily_id>/delete", methods=["POST"])
def homily_delete(homily_id):
    db = get_db()
    db.execute("DELETE FROM homilies WHERE id = ?", (homily_id,))
    db.commit()
    flash("Homily deleted.")
    return redirect(url_for("index"))


def _save_homily(db, homily_id, form):
    values = (
        form.get("type") or "other",
        (form.get("title") or "").strip() or "Untitled",
        (form.get("core_message") or "").strip() or None,
        form.get("body") or None,
        form.get("status") or "draft",
        (form.get("liturgical_day") or "").strip() or None,
        form.get("season") or None,
        form.get("cycle_year") or None,
        (form.get("recording_url") or "").strip() or None,
    )
    if homily_id is None:
        cur = db.execute(
            "INSERT INTO homilies (type, title, core_message, body, status, "
            "liturgical_day, season, cycle_year, recording_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
        homily_id = cur.lastrowid
    else:
        db.execute(
            "UPDATE homilies SET type=?, title=?, core_message=?, body=?, status=?, "
            "liturgical_day=?, season=?, cycle_year=?, recording_url=?, "
            "updated_at=datetime('now') WHERE id=?", values + (homily_id,))
    save_readings(db, homily_id, form)
    save_tags(db, homily_id, form.get("tags"))
    save_illustrations(db, homily_id, form.get("illustrations"))
    save_occasion(db, homily_id, form)
    htype = form.get("type") or "other"
    if htype == "funeral":
        save_funeral(db, homily_id, form)
    else:
        db.execute("DELETE FROM funeral_details WHERE homily_id = ?", (homily_id,))
    if htype in OCCASION_TYPES:
        save_celebration(db, homily_id, form)
    else:
        db.execute("DELETE FROM occasion_details WHERE homily_id = ?", (homily_id,))
    return homily_id


# --------------------------------------------------------------------------
# Congregations
# --------------------------------------------------------------------------
@app.route("/congregations", methods=["GET", "POST"])
def congregations():
    db = get_db()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if name:
            db.execute(
                "INSERT INTO congregations (name, notes) VALUES (?, ?)",
                (name, (request.form.get("notes") or "").strip() or None))
            db.commit()
            flash("Congregation added.")
        return redirect(url_for("congregations"))
    rows = db.execute("SELECT * FROM congregations ORDER BY name").fetchall()
    return render_template("congregations.html", congregations=rows)


@app.route("/congregations/<int:cong_id>/delete", methods=["POST"])
def congregation_delete(cong_id):
    db = get_db()
    db.execute("DELETE FROM congregations WHERE id = ?", (cong_id,))
    db.commit()
    flash("Congregation removed.")
    return redirect(url_for("congregations"))


# --------------------------------------------------------------------------
# The funeral section (specification section 6). Anchored to the person, kept
# apart from the general library.
# --------------------------------------------------------------------------
@app.route("/funerals")
def funerals():
    db = get_db()
    q = request.args.get("q", "").strip()
    only_flagged = request.args.get("flagged") == "1"
    sql = (
        "SELECT h.id, h.title, h.status, h.import_note, "
        "f.deceased_name, f.date_of_death, f.date_of_funeral, f.age, f.about_person "
        "FROM homilies h LEFT JOIN funeral_details f ON f.homily_id = h.id "
        "WHERE h.type = 'funeral'"
    )
    params = []
    if q:
        like = f"%{q}%"
        sql += " AND (f.deceased_name LIKE ? OR h.title LIKE ? OR h.body LIKE ?)"
        params += [like, like, like]
    if only_flagged:
        sql += " AND h.import_note IS NOT NULL"
    # Most recent funerals first; those without a date fall to the bottom.
    sql += (" ORDER BY (f.date_of_funeral IS NULL), f.date_of_funeral DESC, "
            "f.deceased_name COLLATE NOCASE")
    rows = db.execute(sql, params).fetchall()
    flagged_total = db.execute(
        "SELECT COUNT(*) FROM homilies WHERE type='funeral' "
        "AND import_note IS NOT NULL").fetchone()[0]
    return render_template(
        "funerals.html", funerals=rows, total=len(rows),
        flagged_total=flagged_total, q=q, only_flagged=only_flagged,
    )


# --------------------------------------------------------------------------
# Import existing homilies (specification section 10)
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Backing up your homilies. Git keeps the app's code safe; this keeps the one
# file that holds your homilies (database/homilies.db) safe.
# --------------------------------------------------------------------------
def _make_backup(dest_path):
    """Write a consistent snapshot of the database to dest_path using SQLite's
    online-backup API (safe to run while the app is in use)."""
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(dest_path)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()


def _backup_stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _list_backups():
    if not os.path.isdir(BACKUP_DIR):
        return []
    out = []
    for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if name.endswith(".db"):
            p = os.path.join(BACKUP_DIR, name)
            st = os.stat(p)
            out.append({
                "name": name,
                "size_kb": round(st.st_size / 1024),
                "when": datetime.datetime.fromtimestamp(
                    st.st_mtime).strftime("%d %b %Y, %H:%M"),
            })
    return out


@app.route("/backup")
def backup():
    db = get_db()
    counts = {
        "homilies": db.execute("SELECT COUNT(*) FROM homilies").fetchone()[0],
        "funerals": db.execute(
            "SELECT COUNT(*) FROM homilies WHERE type='funeral'").fetchone()[0],
        "stories": db.execute("SELECT COUNT(*) FROM illustrations").fetchone()[0],
    }
    size_kb = round(os.path.getsize(DB_PATH) / 1024) if os.path.exists(DB_PATH) else 0
    return render_template("backup.html", counts=counts, size_kb=size_kb,
                           backups=_list_backups())


@app.route("/backup/download")
def backup_download():
    """Send a fresh snapshot to the browser so you can save it anywhere —
    an external drive, or an iCloud/Dropbox folder for off-machine safety."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        _make_backup(tmp.name)
        with open(tmp.name, "rb") as f:
            data = f.read()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return send_file(
        io.BytesIO(data), as_attachment=True,
        download_name=f"homilies-{_backup_stamp()}.db",
        mimetype="application/x-sqlite3")


@app.route("/backup/save", methods=["POST"])
def backup_save():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dest = os.path.join(BACKUP_DIR, f"homilies-{_backup_stamp()}.db")
    _make_backup(dest)
    flash(f"Backup saved: {os.path.basename(dest)}")
    return redirect(url_for("backup"))


# --------------------------------------------------------------------------
# Export everything to Word or PDF
# --------------------------------------------------------------------------
EXPORT_SCOPES = {
    "all": ("All homilies", "h.status != 'archived'"),
    "library": ("The library",
                "h.type IN ('sunday','weekday','feast','other') AND h.status != 'archived'"),
    "funerals": ("Funerals", "h.type = 'funeral'"),
    "celebrations": ("Weddings & baptisms", "h.type IN ('wedding','baptism')"),
}


def _export_rows(db, scope):
    label, where = EXPORT_SCOPES.get(scope, EXPORT_SCOPES["all"])
    rows = db.execute(
        f"SELECT * FROM homilies h WHERE {where} "
        "ORDER BY h.type, h.cycle_year, h.liturgical_day, h.title"
    ).fetchall()
    out = []
    for r in rows:
        person = None
        if r["type"] == "funeral":
            fd = funeral_for(db, r["id"])
            if fd and fd["deceased_name"]:
                person = fd["deceased_name"]
                if fd["date_of_funeral"]:
                    person += f" — funeral {fd['date_of_funeral']}"
        elif r["type"] in OCCASION_TYPES:
            od = celebration_for(db, r["id"])
            if od and od["people"]:
                person = od["people"]
                if od["event_date"]:
                    person += f" — {od['event_date']}"
        out.append({
            "id": r["id"], "title": r["title"], "type": r["type"],
            "liturgical_day": r["liturgical_day"], "season": r["season"],
            "cycle_year": r["cycle_year"], "status": r["status"],
            "body": r["body"], "person": person,
            "readings": readings_for(db, r["id"]),
            "tags": tags_for(db, r["id"]),
        })
    return out, label


@app.route("/export")
def export_page():
    db = get_db()
    counts = {k: db.execute(
        f"SELECT COUNT(*) FROM homilies h WHERE {w}").fetchone()[0]
        for k, (_lbl, w) in EXPORT_SCOPES.items()}
    return render_template("export.html", scopes=EXPORT_SCOPES, counts=counts)


@app.route("/export/word")
def export_word():
    import exporter
    db = get_db()
    scope = request.args.get("scope", "all")
    homilies, label = _export_rows(db, scope)
    buf = exporter.build_docx(f"Homily Manager — {label}", homilies)
    stamp = datetime.date.today().isoformat()
    return send_file(
        buf, as_attachment=True, download_name=f"homilies-{scope}-{stamp}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.route("/export/print")
def export_print():
    db = get_db()
    scope = request.args.get("scope", "all")
    homilies, label = _export_rows(db, scope)
    return render_template("export_print.html", homilies=homilies, label=label,
                           roles=READING_ROLES)


@app.route("/celebrations")
def celebrations():
    db = get_db()
    q = request.args.get("q", "").strip()
    sql = (
        "SELECT h.id, h.title, h.type, h.status, "
        "o.people, o.event_date, o.family "
        "FROM homilies h LEFT JOIN occasion_details o ON o.homily_id = h.id "
        "WHERE h.type IN ('wedding','baptism')"
    )
    params = []
    if q:
        like = f"%{q}%"
        sql += " AND (o.people LIKE ? OR h.title LIKE ? OR h.body LIKE ?)"
        params += [like, like, like]
    sql += (" ORDER BY (o.event_date IS NULL), o.event_date DESC, "
            "h.title COLLATE NOCASE")
    rows = db.execute(sql, params).fetchall()
    return render_template("celebrations.html", celebrations=rows,
                           total=len(rows), q=q)


@app.route("/import", methods=["GET", "POST"])
def import_page():
    db = get_db()
    summary = None
    if request.method == "POST":
        from importer import run_import
        summary = run_import(db_path=DB_PATH)
        # refresh the derived data so one button keeps everything current
        try:
            import extract_readings
            import extract_stories
            import load_official_lectionary
            extract_readings.backfill_readings(db_path=DB_PATH)
            extract_stories.aggregate(db_path=DB_PATH)
            load_official_lectionary.load_official(db_path=DB_PATH)
        except Exception:
            pass
        flash("Import finished. Readings, stories, and the lectionary were refreshed.")
    stats = {
        "total": db.execute("SELECT COUNT(*) FROM homilies").fetchone()[0],
        "flagged": db.execute(
            "SELECT COUNT(*) FROM homilies WHERE import_note IS NOT NULL"
        ).fetchone()[0],
        "no_text": db.execute(
            "SELECT COUNT(*) FROM homilies WHERE body IS NULL OR length(body) < 20"
        ).fetchone()[0],
    }
    by_type = db.execute(
        "SELECT type, COUNT(*) n FROM homilies GROUP BY type ORDER BY n DESC"
    ).fetchall()
    return render_template(
        "import.html", summary=summary, stats=stats, by_type=by_type)


# --------------------------------------------------------------------------
# The planner (specification sections 7 and 9): the view forward, and the
# three-year lookup of what you preached the last time a Sunday came round.
# --------------------------------------------------------------------------
def _lookup_index(db):
    """Map each Sunday/feast signature to the past homilies for that day, with
    their readings, so the planner can show 'the last time this came round'."""
    index = {}
    rows = db.execute(
        "SELECT id, title, liturgical_day, season, cycle_year, core_message "
        "FROM homilies WHERE type IN ('sunday','feast') AND status != 'archived'"
    ).fetchall()
    for r in rows:
        sig = lectionary.signature(r["season"], r["liturgical_day"] or "")
        if not sig:
            continue
        index.setdefault(sig, []).append({
            "id": r["id"], "title": r["title"], "cycle_year": r["cycle_year"],
            "core_message": r["core_message"],
            "readings": readings_for(db, r["id"]),
        })
    return index


@app.route("/planner")
def planner():
    db = get_db()
    try:
        weeks = max(1, min(52, int(request.args.get("weeks", 16))))
    except ValueError:
        weeks = 16
    today = datetime.date.today()
    sundays = lectionary.upcoming_sundays(today, weeks=weeks)
    index = _lookup_index(db)

    entries = {}
    for row in db.execute("SELECT * FROM planner_entries").fetchall():
        entries[row["scheduled_date"]] = row
    all_series = db.execute("SELECT * FROM series ORDER BY title").fetchall()
    series_by_id = {s["id"]: s["title"] for s in all_series}
    lectionary_idx = {
        (r["signature"], r["cycle_year"]): r
        for r in db.execute("SELECT * FROM lectionary_readings").fetchall()}

    items = []
    for s in sundays:
        iso = s["date"].isoformat()
        sig = lectionary.signature(s["season"], s["label"])
        past = list(index.get(sig, []))
        # same cycle year first (that is the true 3-years-ago homily)
        past.sort(key=lambda h: (h["cycle_year"] != s["cycle_year"],
                                 h["title"].lower()))
        entry = entries.get(iso)
        lect = lectionary_idx.get((sig, s["cycle_year"]))
        items.append({
            "info": s, "iso": iso, "weekday": s["date"].strftime("%a %d %b %Y"),
            "entry": entry, "past": past, "lectionary": lect,
            "series_title": series_by_id.get(entry["series_id"]) if entry else None,
            "same_cycle": [h for h in past if h["cycle_year"] == s["cycle_year"]],
        })

    return render_template(
        "planner.html", items=items, weeks=weeks, all_series=all_series,
        statuses=PLANNER_STATUSES, today=today.isoformat())


@app.route("/planner/save", methods=["POST"])
def planner_save():
    db = get_db()
    iso = request.form["scheduled_date"]
    series_id = request.form.get("series_id") or None
    info = {
        "liturgical_day": request.form.get("liturgical_day") or None,
        "season": request.form.get("season") or None,
        "cycle_year": request.form.get("cycle_year") or None,
        "theme_idea": (request.form.get("theme_idea") or "").strip() or None,
        "status": request.form.get("status") or "not_started",
        "deadline": (request.form.get("deadline") or "").strip() or None,
        "series_id": series_id,
    }
    existing = db.execute(
        "SELECT id FROM planner_entries WHERE scheduled_date = ?", (iso,)
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE planner_entries SET liturgical_day=?, season=?, cycle_year=?, "
            "theme_idea=?, status=?, deadline=?, series_id=? WHERE id=?",
            (info["liturgical_day"], info["season"], info["cycle_year"],
             info["theme_idea"], info["status"], info["deadline"],
             info["series_id"], existing["id"]))
    else:
        db.execute(
            "INSERT INTO planner_entries (scheduled_date, liturgical_day, season, "
            "cycle_year, theme_idea, status, deadline, series_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (iso, info["liturgical_day"], info["season"], info["cycle_year"],
             info["theme_idea"], info["status"], info["deadline"], info["series_id"]))
    db.commit()
    flash("Planner updated.")
    return redirect(url_for("planner") + f"#{iso}")


@app.route("/planner/create-homily", methods=["POST"])
def planner_create_homily():
    """Turn a planner Sunday into a library homily, carrying its day, season,
    year and - if there is a homily from the same cycle three years back - its
    readings, so preparation starts from what was used last time."""
    db = get_db()
    iso = request.form["scheduled_date"]
    day = request.form.get("liturgical_day") or None
    season = request.form.get("season") or None
    cycle = request.form.get("cycle_year") or None
    copy_from = request.form.get("copy_readings_from")

    cur = db.execute(
        "INSERT INTO homilies (type, title, status, liturgical_day, season, "
        "cycle_year) VALUES ('sunday', ?, 'draft', ?, ?, ?)",
        (day or "Untitled", day, season, cycle))
    homily_id = cur.lastrowid

    # Prefer the compiled readings for this day/cycle; fall back to copying from
    # the same-cycle homily three years back.
    sig = lectionary.signature(season, day or "")
    lect = db.execute(
        "SELECT * FROM lectionary_readings WHERE signature = ? AND cycle_year = ?",
        (sig, cycle)).fetchone() if sig else None
    if lect and any(lect[r] for r in
                    ("first_reading", "psalm", "second_reading", "gospel")):
        for role in ("first_reading", "psalm", "second_reading", "gospel"):
            if lect[role]:
                db.execute("INSERT INTO readings (homily_id, role, citation) "
                           "VALUES (?, ?, ?)", (homily_id, role, lect[role]))
    elif copy_from:
        for r in db.execute(
                "SELECT role, citation FROM readings WHERE homily_id = ?",
                (copy_from,)).fetchall():
            db.execute("INSERT INTO readings (homily_id, role, citation) "
                       "VALUES (?, ?, ?)", (homily_id, r["role"], r["citation"]))

    entry = db.execute(
        "SELECT id FROM planner_entries WHERE scheduled_date = ?", (iso,)).fetchone()
    if entry:
        db.execute("UPDATE planner_entries SET homily_id = ? WHERE id = ?",
                   (homily_id, entry["id"]))
    else:
        db.execute(
            "INSERT INTO planner_entries (scheduled_date, liturgical_day, season, "
            "cycle_year, status, homily_id) VALUES (?, ?, ?, ?, 'drafted', ?)",
            (iso, day, season, cycle, homily_id))
    db.commit()
    flash("Created a homily from the planner. It is now in your library.")
    return redirect(url_for("homily_edit", homily_id=homily_id))


# --------------------------------------------------------------------------
# Series: a group of weeks under one theme (specification section 7)
# --------------------------------------------------------------------------
@app.route("/series", methods=["GET", "POST"])
def series_list():
    db = get_db()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if title:
            db.execute("INSERT INTO series (title, description) VALUES (?, ?)",
                       (title, (request.form.get("description") or "").strip() or None))
            db.commit()
            flash("Series created.")
        return redirect(url_for("series_list"))
    rows = db.execute(
        "SELECT s.*, "
        "(SELECT COUNT(*) FROM planner_entries p WHERE p.series_id = s.id) AS weeks "
        "FROM series s ORDER BY s.title").fetchall()
    return render_template("series.html", series=rows)


@app.route("/series/<int:series_id>")
def series_detail(series_id):
    db = get_db()
    s = db.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
    if s is None:
        abort(404)
    weeks = db.execute(
        "SELECT p.*, h.title AS homily_title FROM planner_entries p "
        "LEFT JOIN homilies h ON h.id = p.homily_id "
        "WHERE p.series_id = ? ORDER BY p.scheduled_date", (series_id,)).fetchall()
    return render_template("series_detail.html", series=s, weeks=weeks)


@app.route("/series/<int:series_id>/delete", methods=["POST"])
def series_delete(series_id):
    db = get_db()
    db.execute("DELETE FROM series WHERE id = ?", (series_id,))  # entries kept
    db.commit()
    flash("Series removed. Its weeks are kept in the planner.")
    return redirect(url_for("series_list"))


# --------------------------------------------------------------------------
# The illustration and story bank (specification section 8)
# --------------------------------------------------------------------------
@app.route("/illustrations", methods=["GET", "POST"])
def illustrations():
    db = get_db()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if title:
            db.execute(
                "INSERT INTO illustrations (title, content, source) VALUES (?, ?, ?)",
                (title, (request.form.get("content") or "").strip() or None,
                 (request.form.get("source") or "").strip() or None))
            db.commit()
            flash("Story added.")
        return redirect(url_for("illustrations"))
    q = request.args.get("q", "").strip()
    sql = ("SELECT i.*, "
           "(SELECT COUNT(*) FROM homily_illustrations hi WHERE hi.illustration_id = i.id) AS uses "
           "FROM illustrations i")
    params = []
    if q:
        sql += " WHERE i.title LIKE ? OR i.content LIKE ? OR i.source LIKE ?"
        params += [f"%{q}%"] * 3
    sql += " ORDER BY i.title"
    rows = db.execute(sql, params).fetchall()
    return render_template("illustrations.html", illustrations=rows, q=q)


@app.route("/illustrations/<int:ill_id>")
def illustration_detail(ill_id):
    db = get_db()
    ill = db.execute("SELECT * FROM illustrations WHERE id = ?", (ill_id,)).fetchone()
    if ill is None:
        abort(404)
    used_in = db.execute(
        "SELECT h.id, h.title, h.type FROM homilies h "
        "JOIN homily_illustrations hi ON hi.homily_id = h.id "
        "WHERE hi.illustration_id = ? ORDER BY h.title", (ill_id,)).fetchall()
    # Every time and place it was told, so it is never repeated to the same
    # congregation by accident (specification section 8).
    told = db.execute(
        "SELECT c.name AS congregation, o.date_preached, "
        "h.title AS homily_title, h.id AS homily_id "
        "FROM homily_illustrations hi "
        "JOIN homily_occasions o ON o.homily_id = hi.homily_id "
        "JOIN homilies h ON h.id = hi.homily_id "
        "LEFT JOIN congregations c ON c.id = o.congregation_id "
        "WHERE hi.illustration_id = ? "
        "ORDER BY o.date_preached DESC", (ill_id,)).fetchall()
    return render_template("illustration_detail.html", ill=ill,
                           used_in=used_in, told=told)


@app.route("/illustrations/<int:ill_id>/edit", methods=["POST"])
def illustration_edit(ill_id):
    db = get_db()
    title = (request.form.get("title") or "").strip()
    if title:
        db.execute(
            "UPDATE illustrations SET title=?, content=?, source=? WHERE id=?",
            (title, (request.form.get("content") or "").strip() or None,
             (request.form.get("source") or "").strip() or None, ill_id))
        db.commit()
        flash("Story updated.")
    return redirect(url_for("illustration_detail", ill_id=ill_id))


@app.route("/illustrations/<int:ill_id>/delete", methods=["POST"])
def illustration_delete(ill_id):
    db = get_db()
    db.execute("DELETE FROM illustrations WHERE id = ?", (ill_id,))
    db.commit()
    flash("Story removed.")
    return redirect(url_for("illustrations"))


@app.route("/homily/<int:homily_id>/clear-flag", methods=["POST"])
def homily_clear_flag(homily_id):
    db = get_db()
    db.execute("UPDATE homilies SET import_note = NULL WHERE id = ?", (homily_id,))
    db.commit()
    flash("Review flag cleared.")
    return redirect(url_for("homily_edit", homily_id=homily_id))


if __name__ == "__main__":
    init_db()
    print(f"Homily Manager is running. Open http://127.0.0.1:{PORT} in your browser.")
    app.run(host="127.0.0.1", port=PORT, debug=True)
