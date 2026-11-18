"""Study overview figure (figures/explainer.png): the sources, the real event-level data, and the result.
Every mark is a real trial-event pair. Needs build/selection_event_coverage.csv (from 06_selection_proof.py)."""
import json, pandas as pd, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

X = pd.read_csv('../build/pairs_all_sources.csv')
E = pd.read_csv('../build/selection_event_coverage.csv')
B = pd.read_csv('../results/selection_coverage_by_frequency.csv')
S = pd.read_csv('../results/same_trial_cross_report_summary.csv')
g = S[(S.model == 'GBM') & S.method.str.startswith('A') & (S.trial == 'All trials')].iloc[0]
n_reg = X[X.source.eq('ctgov')].groupby('trial').size(); n_pub = X[X.source.eq('publication')].groupby('trial').size()

BLUE, ORANGE, RED, INK, INK2, GRID, HDR = '#2a78d6', '#eb6834', '#c4314b', '#0b0b0b', '#52514e', '#e6e5e0', '#d9e1f2'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9.5, 'axes.edgecolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.titleweight': 'bold', 'axes.titlesize': 11, 'axes.titlelocation': 'left'})
fig = plt.figure(figsize=(16, 9.4)); fig.patch.set_facecolor('white')
gs = fig.add_gridspec(2, 2, height_ratios=[0.78, 1], width_ratios=[1, 1], hspace=.5, wspace=.24, left=.055, right=.985, top=.9, bottom=.135)
fig.suptitle('Study overview: adverse-event risk differences for the same lupus trials in ClinicalTrials.gov vs the journal article',
             x=.055, ha='left', fontsize=14, fontweight='bold', color=INK)

# ---------------- A. sources table ----------------
a = fig.add_subplot(gs[0, :]); a.axis('off'); a.set_title('A. Trials and sources', loc='left')
cols = ['Trial', 'Registry ID', 'Drug (arms vs placebo)', 'ClinicalTrials.gov\nevent pairs', 'Journal article (table; reporting rule)', 'Article\nevent pairs', 'FDA approval review']
W = [.075, .085, .155, .09, .32, .065, .21]; xs = np.cumsum([0] + W[:-1])
rows = [
 ['TULIP-1', 'NCT02446912', 'anifrolumab IV 150 / 300 mg', n_reg['TULIP-1'], 'Furie 2019, Lancet Rheumatol 1:e208-19 (6 terms; re-verify)', n_pub['TULIP-1'], 'Saphnelo approval review:\ntrials combined, no per-trial counts'],
 ['TULIP-2', 'NCT02446899', 'anifrolumab IV 300 mg', n_reg['TULIP-2'], 'Morand 2020, NEJM 382:211-21, Table 3 (AEs >5% in drug arm)', n_pub['TULIP-2'], 'Saphnelo approval review:\ntrials combined, no per-trial counts'],
 ['BLISS-76', 'NCT00410384', 'belimumab IV 1 / 10 mg/kg', n_reg['BLISS-76'], 'Furie 2011, Arthritis Rheum 63:3918-30, Table 3 (AEs >=10% any arm)', n_pub['BLISS-76'], 'Benlysta approval review:\nscanned pages, text not yet readable'],
 ['BLISS-52', 'NCT00424476', 'belimumab IV 1 / 10 mg/kg', n_reg['BLISS-52'], 'Navarra 2011, Lancet 377:721-31 (not extracted)', 0, 'Benlysta approval review:\nscanned pages, text not yet readable'],
 ['D3461C00008', 'NCT02962960', 'anifrolumab SC, phase 2 (n = 36)', n_reg['SC-phase2 (D3461C00008)'], 'Bruce 2021, Lancet Rheumatol 3:e101-10 (not extracted)', 0, 'None: this injection form was\nnot part of the 2021 approval'],
]
top, rh = .93, .155
for j, c in enumerate(cols):
    a.add_patch(plt.Rectangle((xs[j], top - .12), W[j] - .004, .17, color=HDR, transform=a.transAxes, clip_on=False))
    a.text(xs[j] + .005, top - .035, c, transform=a.transAxes, fontsize=9, fontweight='bold', va='center', color=INK)
for i, r in enumerate(rows):
    y = top - .12 - (i + 1) * rh
    if i % 2 == 0: a.add_patch(plt.Rectangle((0, y), 1, rh, color='#f4f3ef', transform=a.transAxes, clip_on=False))
    for j, v in enumerate(r):
        a.text(xs[j] + .005, y + rh / 2, str(v), transform=a.transAxes, fontsize=9, va='center', color=INK2 if i > 2 else INK,
               fontweight='bold' if j == 0 else 'normal')
a.text(0, top - .12 - 5 * rh - .3,
       'Event pair = one adverse-event term (MedDRA) x one active arm vs placebo x seriousness category.  '
       'Risk difference (RD) = proportion with the event on drug - proportion on placebo.\n'
       'FDA approval review = the document in which the U.S. Food and Drug Administration evaluated the trials before approving the drug '
       '(Saphnelo: BLA 761123, 2021; Benlysta: BLA 125370, 2011).\n'
       'BLISS-52 and D3461C00008 are used for training and calibration only.', transform=a.transAxes, fontsize=8.6, color=INK2, linespacing=1.5)

# ---------------- B. registry RD vs article RD, coloured by coverage ----------------
b = fig.add_subplot(gs[1, 0]); R = E[E.reported].copy()
R['x'], R['y'] = 100 * R.rd, 100 * R.rd_pub
cov = R.cov_ct >= .5
lim = (-7, 14.5)
b.plot(lim, lim, color=INK2, lw=1, ls='--', zorder=1)
b.scatter(R.x[cov], R.y[cov], s=34, color=BLUE, zorder=3, label=f'Inside the 90% interval in most repeats (n={cov.sum()})', edgecolor='white', linewidth=.6)
b.scatter(R.x[~cov], R.y[~cov], s=40, color=RED, zorder=4, label=f'Outside the 90% interval in most repeats (n={(~cov).sum()})', edgecolor='white', linewidth=.6)
lab = {('TULIP-2', 'Upper respiratory tract infection', 'Anifrolumab 300 mg'): ('TULIP-2 URTI, 300 mg', 4.0, 13.3),
       ('TULIP-2', 'Bronchitis', 'Anifrolumab 300 mg'): ('TULIP-2 bronchitis, 300 mg', 9.3, 6.6),
       ('TULIP-1', 'Upper respiratory tract infection', 'Anifrolumab 150 mg'): ('TULIP-1 URTI, 150 mg', 9.3, 4.9),
       ('BLISS-76', 'Headache', 'Belimumab 1 mg/kg'): ('BLISS-76 headache, 1 mg/kg', -6.6, 10.6),
       ('TULIP-2', 'Herpes zoster', 'Anifrolumab 300 mg'): ('TULIP-2 herpes zoster, 300 mg', -6.6, 8.6),
       ('TULIP-1', 'Urinary tract infection', 'Anifrolumab 150 mg'): ('TULIP-1 UTI, 150 mg', -3.4, -6.4)}
for r in R.itertuples():
    k = (r.trial, r.term, r.arm)
    if k in lab:
        t, tx, ty = lab[k]
        b.annotate(t, (r.x, r.y), (tx, ty), fontsize=8.3, color=INK, va='center', arrowprops=dict(arrowstyle='-', color=INK2, lw=.6, shrinkB=3))
b.set_xlim(lim); b.set_ylim(lim)
b.axhline(0, color=GRID, lw=.8, zorder=0); b.axvline(0, color=GRID, lw=.8, zorder=0)
b.set_xlabel('Risk difference in ClinicalTrials.gov (percentage points)'); b.set_ylabel('Risk difference in the journal article (percentage points)')
b.grid(color=GRID, lw=.5); b.legend(frameon=False, loc='lower right', fontsize=8.5)
b.set_title('B. 52 event pairs in both sources: the values agree\n(dashed line = identical); misses are the large risk differences', fontsize=10.5)

# ---------------- C. coverage by event frequency ----------------
c = fig.add_subplot(gs[1, 1]); lab_bins = list(B.fbin); xx = np.arange(len(B)); w = .38
c.bar(xx - w / 2, 100 * B.cov_all, w, color=BLUE, label='All ClinicalTrials.gov event pairs (n = 1,352)')
c.bar(xx + w / 2, 100 * B.cov_paper_registry.fillna(0), w, color=ORANGE, label='Event pairs reported in the article (n = 52)')
for i, r in B.iterrows():
    c.text(i - w / 2, 100 * r.cov_all + 1.5, f'{100 * r.cov_all:.0f}%\nn={r.n_all}', ha='center', fontsize=8, color=INK)
    if r.n_paper == r.n_paper and r.n_paper > 0:
        c.text(i + w / 2, 100 * r.cov_paper_registry + 1.5, f'{100 * r.cov_paper_registry:.0f}%\nn={int(r.n_paper)}', ha='center', fontsize=8, color=INK)
c.axhline(90, color=INK2, ls='--', lw=1); c.text(len(B) - .5, 91.5, 'nominal 90%', ha='right', fontsize=8.5, color=INK2)
c.set_xticks(xx, [f'{b_}' for b_ in lab_bins]); c.set_xlabel('Event frequency: higher of the two arms\' incidence (ClinicalTrials.gov)')
c.set_ylabel('Coverage of 90% conformal interval (%)'); c.set_ylim(0, 135); c.set_yticks(range(0, 101, 20)); c.grid(axis='y', color=GRID)
c.legend(frameon=False, loc='upper right', fontsize=8.5)
c.set_title('C. Coverage falls as events get more frequent;\n48 of the 52 article pairs have frequency >= 5%', fontsize=10.5)

fig.text(.055, .045, f'Method: model trained and calibrated on ClinicalTrials.gov only; event-level 5-fold split within trials; split-conformal 90% interval (alpha = 0.10).\n'
         f'Coverage over 100 repeats: all registry pairs {100 * g.cov_all_registry:.1f}%; article-reported pairs {100 * g.cov_paper_events_registry_values:.1f}% using registry RD, '
         f'{100 * g.cov_paper_events_paper_values:.1f}% using article RD.', fontsize=8.6, color=INK, wrap=True)
fig.text(.055, .012, 'B and C use 40 repeats (scripts/06). Sources: ClinicalTrials.gov API v2 (retrieved 2026-11-18); article tables as listed in A. TULIP-1 article values await re-verification.',
         fontsize=8, color=INK2)
fig.savefig('../figures/explainer.png', dpi=170)
print('saved; reported pairs >=5%:', int((R.freq >= .05).sum()), 'of', len(R), '| misses:', int((~cov).sum()))
