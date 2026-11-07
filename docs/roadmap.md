# Homily Manager — Build Roadmap

This is the order in which to build the app. Each phase leaves you with
something usable, so value arrives early rather than only at the end.

## The tools in use

The app is built to run privately on your own mac, which is why it needs no
login.

- **The app:** Python with the Flask web framework. It runs on your computer and
  opens in your browser.
- **Database:** SQLite, a single file on your mac (`database/homilies.db`). The
  design is in `database/schema.sql`.
- **No hosting and no accounts**, because nothing goes online. If the app is ever
  put online for use from a phone, the same design moves to a hosted PostgreSQL
  database, and a passcode is added at that point.

## Phase 1 — The library and the entry form  (BUILT)

The foundation. Done and tested. It includes:

- The database, created automatically from `database/schema.sql` on first run.
- A form to add and edit a homily: type, title, core message, text, season,
  liturgical day, cycle year, readings, theme tags, and where it was preached.
- A list of homilies with search by text and scripture passage, and filters by
  type, season, year, theme, and congregation.
- The list of congregations you serve.
- No login, because the app runs only on your computer.

You can start adding homilies now. See the README for how to run it.

## Phase 2 — The funeral and occasional section  (BUILT)

- The extra funeral fields: the deceased, dates, age, a note on the person, and
  the family dealt with. Done: the **Funerals** section, with its own list sorted
  by date, a search by name, and the person fields on the homily form.
- Funeral records are kept apart from the general library.
- Done: lighter versions for **weddings and baptisms** — the **Celebrations**
  page, with the couple or the child, the family, and the date, and a homily form
  that shows those fields (with wedding/baptism labels) when you pick the type.

## Phase 3 — The planner and the lectionary  (BUILT)

- Done: the **Planner** page lays out the coming Sundays and feasts, each with
  its liturgical day, season, and cycle year, worked out by `lectionary.py` (a
  full Roman Catholic calendar: Easter computus, Advent/Lent/Easter seasons, the
  numbered Ordinary Time Sundays, and the Sunday solemnities).
- Done: the **three-year lookup** — next to each upcoming Sunday it shows what
  you preached the last time that day came round, pulled from your own library
  and matched by a liturgical "signature", with the same-cycle homily marked and
  its readings shown.
- Done: preparation status, an early theme idea, and a "draft by" deadline on
  each Sunday; and "Start a homily for this Sunday", which creates a library
  homily carrying the day, season, year, and the readings from the same-cycle
  homily three years back.
- Done: **series planning** — group Sundays under one theme (the **Series**
  page), assign a Sunday to a series from the planner, and see the series laid
  out week by week.
- Still to come: pre-loading the full assigned readings for Sundays you have
  never preached before (the lookup covers the ones you have).

## Phase 4 — The illustration and story bank  (BUILT)

- Done: the **Stories** page keeps each illustration once, with its text and
  source. Attach stories to a homily from its "Illustrations / stories used"
  field (like tags); the story's page lists every homily that used it.
- Done: `extract_stories.py` gathered the marked stories out of the imported
  homilies — 184 distinct stories, 40 of them told in more than one homily —
  each linked to the homilies that used it. Re-runnable and self-deduping.
- Done: the story's page shows **every time and place it has been told** (the
  congregation and date from each homily's occasion), so none is repeated to the
  same congregation by accident.

## Reading and formatting

- Each homily now has a **reading view** (click its title) that lays the text out
  in proper paragraphs with comfortable typography, rather than the cramped edit
  box. The importer and a one-time pass fixed the Word line-separator characters
  that made the imported text run together.

## Phase 5 — Import your existing homilies  (BUILT, brought forward)

- Done: the **Import** page reads the six year folders and the FUNERAL HOMILIES
  folder, and creates a library record per file.
- It fills the cycle year from the folder, the liturgical day from the Sunday
  file name, and the funeral date and deceased's name from the funeral file name,
  and pulls each homily's text into the record (Word via macOS `textutil`, PDFs
  via `pypdf`).
- Anything uncertain — unreadable PDFs, non-person reference files, duplicates
  and variants — is imported and flagged **⚑ review** rather than guessed or lost.
- Re-running only adds files that are new (matched by their path), so it is safe
  to repeat.
- The import also reads a **WEDDINGS** folder into the Celebrations section
  (named couples become wedding records; nuptial templates are filed as 'other').
- Readings: filled by `extract_readings.py`, which reads the scripture citations
  out of each homily's text and records the most likely first reading, psalm,
  second reading, and gospel (632 of 759 homilies). A best-effort first pass —
  first reading, psalm, and gospel are usually right; the second reading is the
  least certain — so the priest confirms them on each homily. Re-running only
  fills homilies that have no readings yet, never overwriting edited ones.

## Settled

- **The lectionary.** Roman Catholic, standard lectionary. Readings and the
  A/B/C and I/II cycles can be pre-loaded.
- **How the homily folders are organised.** Six year folders plus a FUNERAL
  HOMILIES folder, with cycle year, liturgical day, and funeral details carried
  in the folder and file names (see the specification, section 10).

## Still open

1. **Whether anyone else will use the app**, such as an assistant or secretary,
   which would affect the login and access rules.
2. **The web framework** for the app itself, to be settled at the start of
   Phase 1.
