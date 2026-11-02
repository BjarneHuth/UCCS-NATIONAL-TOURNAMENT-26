# UCCS Tournament Control Center — Experimental Dynamic NPI

Deploy to Streamlit Community Cloud with `app.py` as the entry point.

Upload all four files at repository root: `app.py`, `dynamic_engine.py`, `data.json`, `requirements.txt`.

Under **Data & Accuracy**, click **Fetch completed 2026 NCAA Division II soccer games**. This calls an unofficial NCAA scoreboard API and may take minutes. Inspect failed dates, unmatched teams and coverage warnings. Then select **Experimental dynamic NPI**. Select tournament game winners; each selection reruns the scenario estimate and changes the rankings and projected field.

**Scientific limitations:** This is a simplified opponent-network calculation, not a reproduction of the official NCAA NPI. It uses baseline-anchored deltas between an estimated network before and after selected games. Team names, DII-only filtering, neutral-site flags, national game completeness, duplicate historical/postseason entries, official formula, and calibration against official NCAA ratings require independent validation. Imported data are kept in the current Streamlit session and may be lost when the server restarts; download a CSV for auditing. Do not report the scenario estimates as official NCAA NPI or qualification probabilities.

The five AQ + five at-large field is a conditional projection, subject to official NCAA rules and eligibility.
