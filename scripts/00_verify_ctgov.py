"""Guardrail: re-download ClinicalTrials.gov adverse-event results and compare them with data/registry_ctgov.csv.
Needs internet access. Exits non-zero if any trial's number of terms or summed affected counts differ.
Usage (from scripts/):  python3 00_verify_ctgov.py"""
import json, sys, urllib.request
import pandas as pd

API = 'https://clinicaltrials.gov/api/v2/studies/{}?fields=resultsSection.adverseEventsModule'
TRIALS = ['NCT02446912', 'NCT02446899', 'NCT00410384', 'NCT00424476', 'NCT02962960']


def live(nct):
    with urllib.request.urlopen(API.format(nct), timeout=60) as r:
        ae = json.load(r)['resultsSection']['adverseEventsModule']
    events = (ae.get('seriousEvents') or []) + (ae.get('otherEvents') or [])
    return len(events), sum((s.get('numAffected') or 0) for e in events for s in (e.get('stats') or []))


def snapshot(nct):
    d = pd.read_csv('../data/registry_ctgov.csv')
    d = d[d.nct_id == nct]
    return len(d) // d.arm.nunique(), int(d.affected.sum())


ok = True
for nct in TRIALS:
    s, l = snapshot(nct), live(nct)
    match = s == l
    ok &= match
    print(f'{nct}: snapshot terms/sum {s}  live {l}  {"MATCH" if match else "DIFFERENT"}')
sys.exit(0 if ok else 1)
