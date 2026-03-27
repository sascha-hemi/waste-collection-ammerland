# Waste Collection Data (Ammerland)

This repository contains JSON data retrieved from the waste management application for the district of Ammerland, Germany. The data describes streets, segments and waste collection schedules used by the official app.

The original response (`awbapp.json`) is delivered by the app as a single JSON string. Internally the string contains 12 blocks separated by the literal `##`. For easier inspection the file has been split into parts under `awbapp_parts/part1.json` ... `part12.json`.

## API Endpoints

The app fetches its data from Firebase Storage. The URL scheme is:

```
https://firebasestorage.googleapis.com/v0/b/abfall-ammerland.appspot.com/o/and%2F{version}%2Fawbapp.json?alt=media
```

| Version | App version | Date range in Kal1 | Notes |
| ------- | ----------- | ------------------- | ----- |
| `and/5/` | ≤ 2.20 | 2018-01-01 – 2024-12-31 | Used in the original `main.py` |
| `and/7/` | 2.21+ | 2024-01-01 – 2026-12-31 | Current endpoint |

The version number in the path is derived from the app's internal `gver = 7` constant (see `MainActivity.java`). When a new year range is needed the provider will likely increment this number again.

## Structure of the JSON Parts

| Part            | Internal name | Description |
| --------------- | ------------- | ----------- |
| **part1.json**  | `Str`         | List of streets. Each object contains `id`, `ortid` (town identifier), `bez` (street name). Towns: 1 Apen, 2 Bad Zwischenahn, 3 Edewecht, 4 Rastede, 5 Westerstede, 6 Wiefelstede. |
| **part2.json**  | `Strgr`       | Street sections (`grenze`). Some streets are split into sections (e.g. `nördl.d. A 28`). Fields: `id`, `strid`, `grenze`. |
| **part3.json**  | `Astgr`       | Additional area-based sections. Format mirrors part2. |
| **part4.json**  | `Strdat`      | Yearly waste schedule per street/section. Key fields: `strid`, `strgrid` (0 = whole street), `resttag`, `restgu`, `biotag`, `biogu`, `werttag`, `wertgu`, `papier`, `vier`, `jahr` (2-digit year). If no entry exists for the current year the most recent one is reused. |
| **part5.json**  | `Astdat`      | Maps streets/sections to internal area codes (`ast`) used by `Kal2`. |
| **part6.json**  | `Kal1`        | **Daily reference table.** One entry per collection day. Fields: `datum` (ISO date), `gu` (even/odd ISO week), `vier` (4-weekly marker), `papier` (paper collection area ID, 0 = none). This is the primary lookup table for scheduling. |
| **part7.json**  | `Kal2`        | Ast- und Strauchwerk dates per town and area code (`ortid`, `datum`, `ast`). |
| **part8.json**  | `Kal3`        | Problemstoffe (hazardous waste) dates per town (`ortid`, `datum`). |
| **part9.json**  | `Fkal`        | Holiday shifts. `datum` is the holiday, `fdatum` is the replacement collection date. |
| **part10.json** | `Poi1`        | Points of interest (recycling centres). Includes coordinates. |
| **part11.json** | `Poi2`        | Waste categories. |
| **part12.json** | `Poi12`       | Relations between points of interest. |

## Decoding Logic

Collection dates are determined by iterating through **Kal1** (part6) and matching each day against the **Strdat** entry (part4) for the selected street/section:

```
weekday  =  Python isoweekday() % 7
             (Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6)

Restabfall:      weekday == resttag  AND  kal1.gu == restgu
                 (+ kal1.vier == strdat.vier  if 4-weekly mode is active)
Bioabfall:       weekday == biotag   AND  kal1.gu == biogu
Gelber Sack:     weekday == werttag  AND  kal1.gu == wertgu
Papier:          kal1.papier == strdat.papier  (direct ID match)
Ast/Strauchwerk: Kal2 entry with matching (ortid, datum, ast)
Problemstoffe:   Kal3 entry with matching (ortid, datum)
```

After matching, holiday shifts from **Fkal** (part9) are applied: if a matched date is listed as `datum` in Fkal, the actual collection takes place on `fdatum` instead.

**Year fallback:** `Strdat` entries carry a `jahr` field (2-digit year). If no entry exists for the current year the app uses the most recent available year — which is why `jahr: 18` (2018-era entries) still work correctly today.

**4-weekly residual waste:** Residents can request a 4-weekly collection interval. In that case the `vier` field in Kal1 acts as an additional filter: only days where `kal1.vier == strdat.vier` are included.

## Example Usage

`main.py` demonstrates how to download the current dataset, look up a street, and print upcoming collection dates. The script uses the correct Kal1-based matching logic documented above.
