-- Homily Manager - database schema (SQLite)
--
-- This is the local, single-user version of the design in docs/specification.md.
-- SQLite keeps the whole database in one file on your mac, so the app needs no
-- server and no login. If the app is ever moved online for several users, this
-- same design can be recreated on PostgreSQL.

PRAGMA foreign_keys = ON;

-- Churches served (specification section 8)
CREATE TABLE IF NOT EXISTS congregations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The library (specification sections 4-6)
CREATE TABLE IF NOT EXISTS homilies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    type            TEXT NOT NULL CHECK (type IN
                        ('sunday','weekday','funeral','wedding','baptism','feast','other')),
    title           TEXT NOT NULL,
    core_message    TEXT,
    body            TEXT,
    status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','ready','preached','archived')),
    liturgical_day  TEXT,
    season          TEXT CHECK (season IN
                        ('advent','christmas','lent','easter','ordinary_time','other')),
    cycle_year      TEXT CHECK (cycle_year IN ('A','B','C','I','II')),
    recording_url   TEXT,
    -- Import provenance (specification section 10). source_file is the original
    -- file this record was read from, used to make re-importing safe (no
    -- duplicates). import_note flags anything the import was unsure about, so it
    -- can be confirmed by hand rather than guessed.
    source_file     TEXT,
    import_note     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
-- The unique index on source_file is created in server.py's migrate(), after
-- the column is guaranteed to exist (older databases predate the column).

-- Each time a homily was preached, and where (specification section 4)
CREATE TABLE IF NOT EXISTS homily_occasions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    homily_id       INTEGER NOT NULL REFERENCES homilies(id) ON DELETE CASCADE,
    congregation_id INTEGER REFERENCES congregations(id) ON DELETE SET NULL,
    date_preached   TEXT,
    notes           TEXT
);

-- Scripture attached to a homily (specification section 5)
CREATE TABLE IF NOT EXISTS readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    homily_id   INTEGER NOT NULL REFERENCES homilies(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN
                    ('first_reading','psalm','second_reading','gospel','other')),
    citation    TEXT NOT NULL
);

-- Extra fields for funeral homilies (specification section 6). Used from Phase 2,
-- but the table is here now so the database is complete.
CREATE TABLE IF NOT EXISTS funeral_details (
    homily_id       INTEGER PRIMARY KEY REFERENCES homilies(id) ON DELETE CASCADE,
    deceased_name   TEXT,
    date_of_death   TEXT,
    date_of_funeral TEXT,
    age             INTEGER,
    about_person    TEXT,
    family_contact  TEXT
);

-- Lighter details for weddings and baptisms (specification section 6): the
-- couple or the child, the family, and the date.
CREATE TABLE IF NOT EXISTS occasion_details (
    homily_id   INTEGER PRIMARY KEY REFERENCES homilies(id) ON DELETE CASCADE,
    people      TEXT,   -- the couple, or the child
    family      TEXT,   -- parents, godparents, families
    event_date  TEXT,   -- date of the wedding or baptism
    note        TEXT
);

-- The Sunday/feast readings table, by cycle year (compiled from the homilies by
-- build_lectionary.py). Lets the planner show the assigned readings for a day.
CREATE TABLE IF NOT EXISTS lectionary_readings (
    signature       TEXT NOT NULL,
    cycle_year      TEXT NOT NULL,
    liturgical_day  TEXT,
    season          TEXT,
    first_reading   TEXT,
    psalm           TEXT,
    second_reading  TEXT,
    gospel          TEXT,
    source          TEXT,
    PRIMARY KEY (signature, cycle_year)
);

-- Illustration and story bank (specification section 8). Used from Phase 4.
CREATE TABLE IF NOT EXISTS illustrations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    content     TEXT,
    source      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS homily_illustrations (
    homily_id       INTEGER NOT NULL REFERENCES homilies(id) ON DELETE CASCADE,
    illustration_id INTEGER NOT NULL REFERENCES illustrations(id) ON DELETE CASCADE,
    PRIMARY KEY (homily_id, illustration_id)
);

-- Theme tags (specification section 8)
CREATE TABLE IF NOT EXISTS tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS homily_tags (
    homily_id   INTEGER NOT NULL REFERENCES homilies(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (homily_id, tag_id)
);

-- A themed group of weeks in the planner (specification section 7). Used from Phase 3.
CREATE TABLE IF NOT EXISTS series (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The planner: the view forward (specification section 7). Used from Phase 3.
CREATE TABLE IF NOT EXISTS planner_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scheduled_date  TEXT NOT NULL,
    liturgical_day  TEXT,
    season          TEXT CHECK (season IN
                        ('advent','christmas','lent','easter','ordinary_time','other')),
    cycle_year      TEXT CHECK (cycle_year IN ('A','B','C','I','II')),
    theme_idea      TEXT,
    status          TEXT NOT NULL DEFAULT 'not_started'
                        CHECK (status IN ('not_started','researching','drafted','ready')),
    deadline        TEXT,
    series_id       INTEGER REFERENCES series(id) ON DELETE SET NULL,
    homily_id       INTEGER REFERENCES homilies(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS planner_readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    INTEGER NOT NULL REFERENCES planner_entries(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN
                    ('first_reading','psalm','second_reading','gospel','other')),
    citation    TEXT NOT NULL
);

-- Indexes for the searches the library does most
CREATE INDEX IF NOT EXISTS idx_homilies_type ON homilies(type);
CREATE INDEX IF NOT EXISTS idx_homilies_season ON homilies(season);
CREATE INDEX IF NOT EXISTS idx_homilies_day ON homilies(liturgical_day);
CREATE INDEX IF NOT EXISTS idx_readings_citation ON readings(citation);
CREATE INDEX IF NOT EXISTS idx_occasions_cong ON homily_occasions(congregation_id);
CREATE INDEX IF NOT EXISTS idx_occasions_date ON homily_occasions(date_preached);
