"""
Homily Manager - the Roman Catholic liturgical calendar (for the planner).

Works out, for any date, which Sunday or principal feast it is: the season, the
liturgical-day name (e.g. "28th Sunday in Ordinary Time"), and the lectionary
cycle year (A/B/C for Sundays). This is what lets the planner lay out the coming
Sundays with their place in the Church's year already filled in, and what lets
the three-year lookup match an upcoming Sunday to the last time it came round.

Standard calendar only (the parish is Roman Catholic on the standard lectionary,
specification section 12). Solemnities that fall on a Sunday are named; Ascension
and Corpus Christi are taken on their Sunday, as in most of the English-speaking
world.
"""

import datetime as _dt
import re as _re

ONE_DAY = _dt.timedelta(days=1)
WEEK = _dt.timedelta(days=7)


def computus(year):
    """Date of Easter Sunday (Gregorian), Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return _dt.date(year, month, day)


def _sunday_on_or_before(d):
    return d - _dt.timedelta(days=(d.weekday() - 6) % 7)


def _sunday_after(d):
    return d + _dt.timedelta(days=(6 - d.weekday()) % 7 or 7)


def first_advent(civil_year):
    """1st Sunday of Advent that starts the liturgical year ending the NEXT
    civil year - the 4th Sunday before Christmas of `civil_year`."""
    christmas = _dt.date(civil_year, 12, 25)
    fourth_advent = _sunday_on_or_before(christmas - ONE_DAY)
    return fourth_advent - 3 * WEEK


def cycle_year(d):
    """Sunday cycle letter A/B/C for the liturgical year containing date d."""
    adv = first_advent(d.year)
    end_year = d.year + 1 if d >= adv else d.year
    return {0: "C", 1: "A", 2: "B"}[end_year % 3]


def weekday_cycle(d):
    """Weekday cycle I/II (I in odd-numbered liturgical years)."""
    adv = first_advent(d.year)
    begin_year = d.year if d >= adv else d.year - 1
    return "I" if begin_year % 2 else "II"


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


class LiturgicalYear:
    """All the anchor dates for the liturgical year that contains `date`."""

    def __init__(self, date):
        adv = first_advent(date.year)
        self.begin_year = date.year if date >= adv else date.year - 1
        self.advent1 = first_advent(self.begin_year)
        self.christmas = _dt.date(self.begin_year, 12, 25)
        ey = self.begin_year + 1
        self.easter = computus(ey)
        self.ash_wednesday = self.easter - _dt.timedelta(days=46)
        self.palm_sunday = self.easter - WEEK
        self.pentecost = self.easter + _dt.timedelta(days=49)
        self.trinity = self.pentecost + WEEK
        self.corpus_christi = self.pentecost + 2 * WEEK
        self.epiphany = _dt.date(ey, 1, 6)
        self.baptism = _sunday_after(self.epiphany)          # Sunday after Epiphany
        self.christ_king = first_advent(ey) - WEEK
        self.next_advent1 = first_advent(ey)

    # -- numbering of Ordinary Time ------------------------------------
    def _ot_part1(self):
        """Sundays in Ordinary Time before Lent, {date: number}. The Sunday
        after the Baptism is the 2nd Sunday in OT."""
        out = {}
        n = 2
        d = _sunday_after(self.baptism)
        while d < self.ash_wednesday:
            out[d] = n
            n += 1
            d += WEEK
        return out

    def _ot_part2(self):
        """Sundays in Ordinary Time after Pentecost, numbered backward so that
        Christ the King is the 34th Sunday."""
        out = {}
        n = 34
        d = self.christ_king
        while d > self.pentecost:
            out[d] = n
            n -= 1
            d -= WEEK
        return out


def classify(date):
    """Return a dict describing the Sunday/feast on `date`, or None if `date`
    is not a Sunday that the planner lists (only Sundays and a few solemnities
    that fall on Sundays are returned)."""
    ly = LiturgicalYear(date)
    cyc = cycle_year(date)

    def entry(season, label, solemnity=False, ot=None):
        return {
            "date": date, "season": season, "label": label,
            "cycle_year": cyc, "solemnity": solemnity, "ot_number": ot,
        }

    # Fixed-date solemnities that outrank the Sunday
    if date == _dt.date(date.year, 12, 25):
        return entry("christmas", "The Nativity of the Lord (Christmas)", True)
    if (date.month, date.day) == (1, 1):
        return entry("christmas", "Mary, the Holy Mother of God", True)

    if date.weekday() != 6:          # not a Sunday
        return None

    # Advent
    if ly.advent1 <= date < ly.christmas:
        wk = (date - ly.advent1).days // 7 + 1
        return entry("advent", f"{_ordinal(wk)} Sunday of Advent")

    # Christmas season
    if ly.christmas <= date < ly.baptism:
        if date == ly.baptism:
            pass
        # Holy Family: Sunday in the octave of Christmas
        if ly.christmas < date <= _dt.date(ly.begin_year, 12, 31):
            return entry("christmas", "The Holy Family")
        if date <= ly.epiphany + _dt.timedelta(days=6):
            return entry("christmas", "The Epiphany of the Lord", True)
    if date == ly.baptism:
        return entry("christmas", "The Baptism of the Lord")

    # Lent
    if ly.ash_wednesday <= date < ly.easter:
        if date == ly.palm_sunday:
            return entry("lent", "Palm Sunday of the Passion of the Lord", True)
        wk = (date - _sunday_after(ly.ash_wednesday)).days // 7 + 1
        if date < ly.palm_sunday:
            return entry("lent", f"{_ordinal(wk)} Sunday of Lent")

    # Easter season
    if ly.easter <= date <= ly.pentecost:
        if date == ly.easter:
            return entry("easter", "Easter Sunday of the Resurrection", True)
        if date == ly.pentecost:
            return entry("easter", "Pentecost Sunday", True)
        wk = (date - ly.easter).days // 7 + 1
        return entry("easter", f"{_ordinal(wk)} Sunday of Easter")

    # Ordinary Time solemnities on Sundays
    if date == ly.trinity:
        return entry("ordinary_time", "The Most Holy Trinity", True)
    if date == ly.corpus_christi:
        return entry("ordinary_time", "The Most Holy Body and Blood of Christ", True)
    if date == ly.christ_king:
        return entry("ordinary_time",
                     "Our Lord Jesus Christ, King of the Universe", True, ot=34)

    # Ordinary Time numbered Sundays
    p1, p2 = ly._ot_part1(), ly._ot_part2()
    if date in p1:
        n = p1[date]
        return entry("ordinary_time", f"{_ordinal(n)} Sunday in Ordinary Time", ot=n)
    if date in p2:
        n = p2[date]
        return entry("ordinary_time", f"{_ordinal(n)} Sunday in Ordinary Time", ot=n)

    # A Sunday not otherwise caught (e.g. 2nd Sunday after Christmas)
    if ly.christmas <= date < ly.ash_wednesday:
        return entry("christmas", "2nd Sunday after the Nativity")
    return entry("ordinary_time", "Sunday")


def signature(season, text):
    """A short key identifying which Sunday/feast of the year this is, so an
    upcoming Sunday can be matched to past homilies for the same day even though
    their names were typed many different ways. e.g. "ot28", "advent3", "lent5",
    "easter2", "christ_king", "pentecost"."""
    t = (text or "").lower()
    pairs = [
        ("christ_king", ("king of the universe", "christ the king")),
        # Corpus Christi before Trinity: the Year A label reads "Sunday after
        # Trinity Sunday: ... Body and Blood ...", so the more specific match wins.
        ("corpus_christi", ("body and blood", "corpus christi")),
        ("trinity", ("holy trinity", "trinity sunday")),
        ("pentecost", ("pentecost",)),
        ("palm", ("palm sunday", "passion")),
        ("easter_day", ("easter sunday", "resurrection")),
        ("baptism", ("baptism of the lord",)),
        ("holy_family", ("holy family",)),
        ("epiphany", ("epiphany",)),
        ("mary_mother", ("mother of god",)),
        ("ascension", ("ascension",)),
        ("christmas", ("nativity", "christmas")),
    ]
    for key, needles in pairs:
        if any(n in t for n in needles):
            return key
    m = _re.search(r"(\d{1,2})\s*(?:st|nd|rd|th)?", t)
    n = m.group(1) if m else ""
    if "advent" in t or season == "advent":
        return f"advent{n}" if n else None
    if "lent" in t or season == "lent":
        return f"lent{n}" if n else None
    if "easter" in t or season == "easter":
        return f"easter{n}" if n else None
    if n:
        return f"ot{n}"      # Ordinary Time by default
    return None


def upcoming_sundays(start, weeks=16):
    """List of classify() dicts for the Sundays (and Sunday solemnities) in the
    `weeks` weeks from `start`."""
    out = []
    d = _sunday_after(start - ONE_DAY) if start.weekday() != 6 else start
    end = start + _dt.timedelta(weeks=weeks)
    while d <= end:
        info = classify(d)
        if info:
            out.append(info)
        d += WEEK
    return out
