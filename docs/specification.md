# Homily Manager — Specification

This document records the full design of the application as we have discussed
it. It is the reference for everything the app should hold and do. The database
schema in `database/schema.sql` turns this design into tables, and the roadmap
in `roadmap.md` turns it into a build order.

## 1. Purpose

A private workspace for a priest who preaches across more than one congregation.
It keeps every homily you have ever preached in one searchable place, and it
helps you prepare the ones still ahead. Nothing you write is lost, and anything
you have said before is a few seconds away when you need it again.

## 2. The core idea: two views of the same records

The app has two faces that share one set of records.

The **library** looks backward. It holds every homily you have already
preached, sorted and searchable.

The **planner** looks forward. It lays out the Sundays and feasts still to come,
with their readings ready, so you can prepare in good time.

A homily usually begins as an entry in the planner. Once you have delivered it,
it settles into the library. The same record moves from one view to the other,
so you never retype anything.

## 3. Types of homily

Every homily belongs to a type, because different occasions need different
details:

- **Sunday** — tied to the three-year lectionary cycle (Year A, B, or C)
- **Weekday** — tied to the two-year weekday cycle (Year I or II)
- **Funeral** — tied to a person, not a date in the cycle
- **Wedding** — an occasional homily
- **Baptism** — an occasional homily
- **Feast or solemnity** — a named feast outside the ordinary Sundays
- **Other** — retreats, novenas, special services

Sunday and weekday homilies sit inside the Church's calendar. The rest are
called occasional homilies, and funerals are the most important of these to keep
well.

## 4. The homily record — fields common to all types

Every homily, whatever its type, holds:

**Identity**
- Title or one-line summary
- Core message: the single thing you wanted people to carry home, in one
  sentence
- Full text, or your outline and notes
- Status: draft, ready, preached, or archived
- A link to an audio or video recording, if one exists

**Place in the Church's year** (used mainly by Sunday and weekday homilies)
- Liturgical day or occasion (for example, "3rd Sunday of Advent")
- Season: Advent, Christmas, Lent, Easter, Ordinary Time, or other
- Lectionary year: A, B, or C for Sundays; I or II for weekdays; left empty for
  occasional homilies

**Where and when it was preached**
- A homily can be preached more than once, at different congregations and on
  different dates. Each occasion is recorded on its own, with the congregation,
  the date, and any notes for that occasion. This is how the app knows a homily
  has already been heard at a particular parish.

**Threads that are easy to lose**
- Illustrations and stories used (see section 8)
- Theme tags such as mercy, forgiveness, stewardship, suffering, vocation

## 5. Scripture readings

Each homily records the readings it was built on, each stored by its reference:

- First reading
- Responsorial psalm
- Second reading
- Gospel
- Any other passage used

Storing readings this way lets you later search the whole library by passage.
Open to Luke 15 and you see every homily that has ever touched it.

## 6. Funeral and occasional homilies — the extra fields

A funeral homily is anchored to a person, so it carries its own details on top
of the common fields above:

- Name of the deceased
- Date of death and date of the funeral Mass
- Age
- A short note on who they were and their place in the parish, so the person
  comes back to you when you read it again
- The family or chief mourner you dealt with, which also helps when you later
  minister to that same family
- The readings chosen, since funerals usually draw from a set list the family
  picks
- Theme tags such as grief, resurrection, hope, eternal life

Kept this way, the funeral homilies become a quiet pastoral record. When you sit
with a grieving family you can recall exactly what you preached at their
mother's funeral, and over the years you can see which words of comfort and
which readings you return to.

Weddings and baptisms use a lighter version of the same idea: the names of the
couple or the child and family, the date, and the readings chosen.

## 7. The planner — the view forward

The planner is a calendar of the Sundays and feasts coming up. For each date it
shows:

- The liturgical day, its season, and the year of the cycle
- The assigned readings, filled in for you rather than looked up by hand each
  week
- A space for your early idea or chosen theme
- A preparation status: not started, researching, drafted, or ready
- An optional deadline, so a Sunday can be marked "draft by Thursday"

When you finish preparing an entry, it becomes a library homily with a couple of
clicks, carrying its readings and date across.

The planner is also where you plan a **series**. You group several weeks under
one theme, give the series a title, and assign each week its part, so a stretch
on the sacraments or the beatitudes is laid out as a whole rather than invented
Sunday by Sunday.

## 8. Supporting pieces

**Illustration and story bank.** A good story lives in one place here, separate
from any single homily but linked to every homily that used it. Each record
shows the story, its source, and every time and place you have told it, so you
never repeat the same story to the same congregation by accident.

**Scripture index.** This is simply the library sorted by Bible passage. It
answers "what have I said on this text" across all the years at once.

**Tag list.** You control the list of themes, so a search for "stewardship"
catches everything rather than missing the ones once tagged "giving."

**Congregations.** The list of the churches you serve, so every homily occasion
can be tied to the right one.

## 9. The feature that makes it worth building

The Catholic Sunday lectionary runs on a three-year cycle. The readings you
preach this Sunday come round again in exactly three years. Because every homily
records its liturgical day, the planner can show you, next to an upcoming
Sunday, what you preached the last time that same day came up — three years ago,
six years ago, and so on. You see the old homily, the story you told, and the
point you made, and you decide whether to deepen it or go a different way. Over a
few years this becomes a real record of how your preaching on each text has
grown.

## 10. Importing your existing homilies

Your homilies are already in a folder called "HOMILY MANAGER", organised like
this:

- Six folders, one per liturgical year, named by their span and cycle year:
  "2020 - 2021 HOMILIES YEAR B" through "2025 - 2026 HOMILIES YEAR A". Together
  they hold roughly 550 Sunday and weekday homilies.
- A "FUNERAL HOMILIES" folder of about 220 homilies.
- Files are mostly Word (.docx), with some older .doc and a few PDFs.

This layout carries most of what the import needs in the folder and file names
themselves:

- The **year folder** gives the cycle year (A, B, or C) for every homily inside
  it.
- A **Sunday filename** gives the liturgical day, for example "11th Sunday
  Ordinary Time Year B".
- A **funeral filename** gives the date and the name of the deceased, for
  example "12th October 2023 - Funeral of Martin Bouchie".

The import will therefore:

1. Read each file and create a library record.
2. Fill in the cycle year from the folder, the liturgical day from the Sunday
   filename, and the funeral date and deceased name from the funeral filename.
3. Pull the homily text out of the Word or PDF file into the record's body.
4. Flag duplicates and variants for you — some Sundays have more than one file
   (marked "Old", "LATEST", or "2") — so you can keep the right one and link the
   rest rather than lose any.
5. Leave anything uncertain for you to confirm, rather than guessing. Readings
   are usually inside the text rather than the filename, so those may need a
   light pass.

Funeral homilies import straight into the funeral section.

## 11. Privacy and security

Funeral records hold personal details of the dead and the bereaved, and the
library as a whole is your own pastoral work. The app is private to you and sits
behind a login. Funeral and other occasional records are not for general
viewing. If the app ever gains other users, such as an assistant or a secretary,
their access is limited to what they need.

## 12. Settled and still open

- **Settled:** the congregation is Roman Catholic and follows the standard
  lectionary, so the readings and the A/B/C and I/II cycles can be pre-loaded.
- **Settled:** the existing homilies live in the "HOMILY MANAGER" folder, with
  funeral homilies in their own "FUNERAL HOMILIES" folder (see section 10).
- The app is a web application reachable from any phone or computer, so your
  records travel with you. The roadmap proposes the specific tools.
