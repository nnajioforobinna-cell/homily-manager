# Homily Manager

A private application for a priest who preaches across more than one
congregation. It keeps every homily you have ever preached in one searchable
place, and it will help you prepare the ones still ahead. Funeral homilies have
their own section, anchored to the person rather than the calendar.

The app runs on your own mac and opens in your web browser. It stays entirely on
your computer: no account, no login, nothing on the internet. Your homilies and
your funeral records never leave your machine.

## What is in this folder

**The working app (Phase 1)**

- `server.py` — the application itself.
- `templates/` — the pages you see in the browser.
- `static/style.css` — the look of those pages.
- `database/schema.sql` — the design of the database.
- `requirements.txt` — the one thing the app needs installed (Flask).
- `tests/smoke_test.py` — a quick self-check that the app works.

**The plan**

- `docs/specification.md` — the full design of the whole app, all phases.
- `docs/roadmap.md` — the build order and what each phase adds.

## Running the app

**The easiest way:** open the `app` folder in Finder and double-click
`start.command`. The first time, it quietly sets itself up, then it starts the
app and opens it in your browser. Nothing to type. If macOS ever says it cannot
verify the file, right-click `start.command`, choose Open, then Open again.

To stop the app, close the window that opened, or press Control-C in it.

**If you would rather do it by hand** (Python 3 is already on your mac):

1. Open this `app` folder in a terminal.
2. `pip3 install -r requirements.txt`
3. `python3 server.py`
4. Open `http://127.0.0.1:5050` in your browser.

The first run creates your database at `database/homilies.db`. That file is your
library.

## Using it

- **Congregations** — add your parish first, so homilies can be tied to it.
- **+ New homily** — add a homily: its type, title, core message, liturgical
  day, season and year, readings, text, theme tags, and where it was preached.
- **Library** — every homily except funerals, with search by text or scripture
  passage, and filters by type, season, year, theme, and congregation. Old copies
  you have archived are hidden unless you tick "Show archived".
- **Planner** — the Sundays and feasts ahead, each with its liturgical day,
  season, and cycle year worked out for you, and — next to each — what you
  preached the last time that same day came round three years ago, with its
  readings. Jot an early theme, set a "draft by" date, or start a homily for a
  Sunday in one click.
- **Series** — group several Sundays under one theme (a stretch on the
  beatitudes, say); assign a Sunday to a series from the Planner.
- **Stories** — the illustration and story bank: keep a story once, attach it to
  the homilies that used it, and see every time and place you have told it, so
  you never repeat the same story to the same congregation.
- **Funerals** — the funeral homilies on their own, anchored to the person, with
  the name, the dates, the age, a note on who they were, and the family you dealt
  with. Kept apart from the general library.
- **Celebrations** — weddings and baptisms, the lighter occasional homilies: the
  couple or the child, the family, and the date.
- **Import** — read your existing homily folders into the library (see below).

Click any homily's title to **read it** in a clean, properly formatted view;
the Edit button takes you to the form.

## What is working now, and what comes next

Built so far: the library and reading view, the entry form, search and filters,
congregations, the funeral section, the import of your existing homilies, the
planner with the lectionary and the three-year lookup, series planning, and the
illustration and story bank, and the weddings-and-baptisms section. What remains,
in `docs/roadmap.md`, is small: pre-loading the assigned readings for Sundays you
have never preached before (the three-year lookup already covers the ones you
have).

## Your homilies, now imported

Your existing homilies live in the "HOMILY MANAGER" folder on this mac: six year
folders of Sunday and weekday homilies, and a "FUNERAL HOMILIES" folder. The
**Import** page reads them all in — it fills the cycle year from the folder, the
liturgical day from the Sunday file name, and the funeral date and name from the
funeral file name, and pulls the text of each homily into the record. Word
(`.docx`, `.doc`) files are read in full; a few PDFs it cannot read are brought
in and flagged so you can paste their text by hand.

Nothing is thrown away. Anything the import is unsure about — a file that is not
a homily for one person, a duplicate marked "Old" or "LATEST", a name it could
not read — is imported and marked **⚑ review**, so you confirm it rather than the
import guessing. Open the Library and the Funerals section, filter to the
flagged ones, and clear each once it looks right. Running the import again only
adds files that are new, so it is safe to repeat as you add more.

## Where things stand

The congregation is Roman Catholic on the standard lectionary, so the planner
will pre-load each Sunday's readings and the A/B/C and I/II cycles. The app is
for you alone and has no login, because it runs only on your computer. If you
ever want it on your phone as well, that is a later change, and it would then
need at least a passcode because of the personal details in the funeral records.
