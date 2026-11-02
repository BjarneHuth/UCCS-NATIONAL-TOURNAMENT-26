# UCCS Tournament Control Center — Streamlit

A standalone, browser-based version of the Super Region 4 conference tournament scenario model. No Colab or visible code required for viewers.

## Run on your computer

1. Unzip the project.
2. Open Terminal in the `uccs_streamlit` folder.
3. Install dependencies: `python3 -m pip install -r requirements.txt`
4. Launch: `python3 -m streamlit run app.py`
5. Open the local URL printed by Streamlit (normally http://localhost:8501).

## Share as a website

Upload `app.py`, `data.json`, and `requirements.txt` to a GitHub repository. Then go to https://share.streamlit.io/ , sign in, choose **Create app**, select your repository and `app.py`, and deploy. The resulting link is a normal website. The app is public if deployed publicly; avoid uploading private team data.

## What works

- Five conference bracket editors; selecting a winner advances that team and clears invalid downstream selections.
- 10-team projected field: 5 conference champions plus 5 at-large teams selected using current ratings.
- Top 20 regional teams plus remaining bracket contenders, rooting guide, scenario enumeration.
- NPI manual editing, downloadable/restorable scenario JSON.

## Critical limitation

The model is **fixed NPI** until current ratings are manually entered. It does not include a complete nationwide game database, validated NCAA NPI formula, automatic score import, or official selection odds. Scenario fractions assume all unresolved outcomes equally likely. The starting team ratings and brackets are the earlier Nov 1, 2026 project snapshot; verify schedule and eligibility before relying on it.

The website does not persist picks across users or sessions. Download the scenario JSON and upload it later to restore picks.
