# Sample "bring your own data" files

These files show what AURA's CSV import (**⬆ Import** in the crew sidebar) accepts beyond the
simple template. **They are synthetic test data**, written to look like real exports, and are
not measurements of any real person. `backend/tests/test_custom_data.py` imports every one of
them through the API and checks every panel still works.

| File | Looks like | What it exercises |
| --- | --- | --- |
| `wearable_export.csv` | A smartwatch app export | `Date` column with ISO timestamps, units in headers (`Resting Heart Rate (bpm)`), `97%` in cells, sleep in **minutes**, `Active Minutes` mapped to exercise, extra columns (`Steps`, `HRV (ms)`) |
| `clinic_visits_eu.csv` | Weekly clinic visits typed into Excel in a European locale | `;` separator, decimal commas, `DD.MM.YYYY` dates, blood pressure as `118/76`, glucose in **mmol/L**, a `Notes` column, sparse readings |
| `lab_results_long.csv` | A lab or device log, one row per reading | Long layout (`date,test,value,unit`), heart rate twice a day (averaged), temperature in **°F**, dosimeter reads in **µSv** twice a day (summed), a short fever on mission days 20–25 |
| `analog_mission_60d.csv` | A full analog-habitat participant | Day numbers, all ten built-in indicators plus `body_weight` and `hrv`, 14 preflight and 60 mission days. Exercise slips first, then weight, HRV, heart rate and mood follow |
| `custom_indicators.json` | Definitions for **Body weight**, **HRV** and **Grip strength** | POST each object to `/api/indicators` (or enter it with **+ Add indicator**) before importing, so those columns are kept instead of skipped |

## Try it

1. Optional: add the custom indicators from `custom_indicators.json` with **+ Add indicator**.
2. Click **⬆ Import**, choose a file and, for the three files with dates, set **Launch date** to
   **2026-10-01** (the date that becomes mission day 1).
3. AURA adds the person to the crew and lists what it converted, averaged or skipped.

Without a launch date, dates are matched to the mission's own start date, and the notice says how
many preflight and mission days that gave.
