import json
import datetime

import requests

# Current endpoint (app version 2.21+, gver=7)
# Previous endpoint (app <= 2.20): and/5/awbapp.json
URL = "https://firebasestorage.googleapis.com/v0/b/abfall-ammerland.appspot.com/o/and%2F7%2Fawbapp.json?alt=media"

# Town name -> ortid
CITY_MAP = {
    "Apen": 1,
    "Bad Zwischenahn": 2,
    "Edewecht": 3,
    "Rastede": 4,
    "Westerstede": 5,
    "Wiefelstede": 6,
}

# Waste type labels (bitmask) matching the app's MKalText() output
WASTE_TYPES = {
    1:  "Restabfall",
    2:  "Bioabfall",
    4:  "Gelber Sack",
    8:  "Papier",
    16: "Ast- und Strauchwerk",
    32: "Problemstoffe",
}


def load_data():
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    blocks = response.text.split("##")
    return [json.loads(b) for b in blocks if b.strip()]


def select_city():
    print("Gemeinden:")
    for name, oid in CITY_MAP.items():
        print(f"  {oid}: {name}")
    ortid = int(input("Gemeinde-ID eingeben: "))
    name = next(n for n, i in CITY_MAP.items() if i == ortid)
    return ortid, name


def select_street(parts, ortid):
    streets = [s for s in parts[0] if s["ortid"] == ortid]
    print(f"\nStrassen ({len(streets)} gesamt) - Anfangsbuchstabe zum Filtern oder Enter fuer alle:")
    letter = input("Buchstabe: ").strip().upper()
    filtered = [s for s in streets if not letter or s["bez"].upper().startswith(letter)]
    for s in filtered:
        print(f"  {s['id']}: {s['bez']}")
    street_id = int(input("Strassen-ID eingeben: "))
    return next(s for s in streets if s["id"] == street_id)


def select_section(parts, street_id):
    sections = [s for s in parts[1] if s["strid"] == street_id]
    if not sections:
        return 0
    print("\nAbschnitte:")
    for s in sections:
        print(f"  {s['id']}: {s['grenze']}")
    return int(input("Abschnitts-ID eingeben (0 = gesamte Strasse): "))


def get_strdat(parts, street_id, strgrid):
    """Return the most recent Strdat entry for this street/section."""
    candidates = [
        e for e in parts[3]
        if e["strid"] == street_id and e["strgrid"] == strgrid
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e["jahr"])


def get_ast(parts, street_id, strgrid):
    """Return the ast area code for Kal2 lookup."""
    entry = next(
        (e for e in parts[4] if e["strid"] == street_id and e["astgrid"] == strgrid),
        None,
    )
    if entry is None and strgrid != 0:
        entry = next(
            (e for e in parts[4] if e["strid"] == street_id and e["astgrid"] == 0),
            None,
        )
    return entry["ast"] if entry else None


def get_collection_dates(parts, ortid, sd, ast, four_weekly_rest=False):
    """
    Match collection dates from Kal1 (part6) against the Strdat entry (part4).

    Weekday encoding — Java Calendar.DAY_OF_WEEK - 1, identical to isoweekday() % 7:
        Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6
    """
    kal1 = parts[5]
    kal2 = parts[6]
    kal3 = parts[7]
    fkal = parts[8]

    holiday_shift = {e["datum"]: e["fdatum"] for e in fkal}
    results = []

    for entry in kal1:
        date_str = entry["datum"]
        gu    = entry["gu"]
        vier  = entry["vier"]
        papier = entry["papier"]

        dow = datetime.date.fromisoformat(date_str).isoweekday() % 7
        mart = 0

        if dow == sd["resttag"] and gu == sd["restgu"]:
            if not four_weekly_rest or vier == sd["vier"]:
                mart |= 1   # Restabfall
        if dow == sd["biotag"]  and gu == sd["biogu"]:
            mart |= 2       # Bioabfall
        if dow == sd["werttag"] and gu == sd["wertgu"]:
            mart |= 4       # Gelber Sack
        if papier != 0 and papier == sd["papier"]:
            mart |= 8       # Papier

        if mart == 0:
            continue

        actual = datetime.date.fromisoformat(holiday_shift.get(date_str, date_str))
        for bit in (1, 2, 4, 8):
            if mart & bit:
                results.append((actual, WASTE_TYPES[bit]))

    # Ast- und Strauchwerk from Kal2
    if ast is not None:
        for entry in kal2:
            if entry["ortid"] == ortid and entry["ast"] == ast:
                d = entry["datum"]
                actual = datetime.date.fromisoformat(holiday_shift.get(d, d))
                results.append((actual, "Ast- und Strauchwerk"))

    # Problemstoffe from Kal3
    for entry in kal3:
        if entry["ortid"] == ortid:
            d = entry["datum"]
            actual = datetime.date.fromisoformat(holiday_shift.get(d, d))
            results.append((actual, "Problemstoffe"))

    return sorted(results, key=lambda x: x[0])


def main():
    print("Daten werden geladen ...")
    parts = load_data()
    print(f"Kal1-Zeitraum: {parts[5][0]['datum']} bis {parts[5][-1]['datum']}\n")

    ortid, city_name = select_city()
    street = select_street(parts, ortid)
    strgrid = select_section(parts, street["id"])

    four_weekly = input("\n4-woechentlicher Restabfallrhythmus beantragt? (j/n): ").strip().lower() == "j"

    sd = get_strdat(parts, street["id"], strgrid)
    if sd is None:
        print("Kein Abfuhrplan gefunden.")
        return

    ast = get_ast(parts, street["id"], strgrid)
    section_info = f" (Abschnitt {strgrid})" if strgrid else ""
    print(f"\nAbfuhrtermine fuer {city_name} - {street['bez']}{section_info}:\n")

    dates = get_collection_dates(parts, ortid, sd, ast, four_weekly)
    today = datetime.date.today()
    upcoming = [(d, t) for d, t in dates if d >= today]

    for d, t in upcoming[:30]:
        print(f"  {d.strftime('%d.%m.%Y')}  {t}")

    print(f"\n({len(upcoming)} Termine ab heute, {len(dates)} gesamt im Datensatz)")


if __name__ == "__main__":
    main()
    get_abfalltermine(ortid, street_id, street_name)