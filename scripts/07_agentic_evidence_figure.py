"""Companion figure: why this study needs an agentic workflow, and why the agent needs guardrails.
Every number is read from this project's own files or from events logged during the 2026-11-18 session
(see README). No time savings or accuracy rates are claimed - those are to be measured during the fellowship."""
import pandas as pd, numpy as np, textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

O = '../results/'
X = pd.read_csv('../build/pairs_all_sources.csv')
S = pd.read_csv(O + 'source_differences_and_misses.csv')
T = pd.read_csv(O + 'same_trial_cross_report_summary.csv')
cnt = X.groupby(['trial', 'source']).size().unstack(fill_value=0)
# registry vs paper pairs for trials whose paper table was fully extracted
tr = ['BLISS-76', 'TULIP-2']
reg = [int(cnt.loc[t, 'ctgov']) for t in tr]; pub = [int(cnt.loc[t, 'publication']) for t in tr]
# consequence 1: mislabeled trial (earlier dataset called NCT02962960 "TULIP-2")
g = T[(T.model == 'GBM') & T.method.str.startswith('A')].set_index('trial')
cov_real, cov_mis = 100 * g.loc['TULIP-2', 'cov_all_registry'], 100 * g.loc['SC-phase2 (D3461C00008)', 'cov_all_registry']
# consequence 2: automated PDF reader returned two different herpes zoster counts for the same pooled population
rd_a = 75 / 459 - 44 / 466; rd_b = 28 / 459 - 6 / 466
pdf_gap = 100 * abs(rd_a - rd_b)
med_real, max_real = S.abs_rd_diff_pp.median(), S.abs_rd_diff_pp.max()
n_differ = int(((S.a_ct != S.a_pub) | (S.c_ct != S.c_pub)).sum()); n_pairs = len(S)

BLUE, ORANGE, GRAY, INK, INK2, GRID = '#2a78d6', '#eb6834', '#9a9891', '#0b0b0b', '#52514e', '#e6e5e0'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.titleweight': 'bold', 'axes.titlesize': 11, 'axes.titlelocation': 'left'})
fig = plt.figure(figsize=(15, 10.2)); fig.patch.set_facecolor('white')
gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.45], hspace=.42, wspace=.38, left=.06, right=.98, top=.845, bottom=.04)

# A. scale: what a paper-only extraction sees
a = fig.add_subplot(gs[0, 0]); y = np.arange(len(tr)); h = .36
a.barh(y + h / 2, reg, h, color=BLUE, label='Registry (pulled by agent)')
a.barh(y - h / 2, pub, h, color=ORANGE, label='Journal article table')
for i in range(len(tr)):
    a.text(reg[i] + 8, y[i] + h / 2, f'{reg[i]}', va='center', fontsize=9, color=INK)
    a.text(pub[i] + 8, y[i] - h / 2, f'{pub[i]}  ({100 * pub[i] / reg[i]:.0f}% of registry)', va='center', fontsize=9, color=INK)
a.set_yticks(y, tr); a.invert_yaxis(); a.set_xlim(0, max(reg) * 1.45); a.set_xlabel('Drug-vs-placebo event pairs reported')
a.grid(axis='x', color=GRID); a.legend(frameon=False, loc='lower right', fontsize=8.5)
a.set_title('A. Papers show a small, selected slice;\nthe full record needs registry-scale retrieval', fontsize=11)

# B. consequence of a mislabeled trial
b = fig.add_subplot(gs[0, 1])
b.bar([0, 1], [cov_real, cov_mis], .55, color=[BLUE, GRAY])
for i, v in enumerate([cov_real, cov_mis]): b.text(i, v - 7, f'{v:.0f}%', ha='center', fontsize=11, color='white', fontweight='bold')
b.set_xticks([0, 1], ['Real TULIP-2\nNCT02446899\n(180 vs 182 pts)', 'Trial wrongly labeled\n"TULIP-2" in earlier data\n(NCT02962960, 9-14 pts/arm)'], fontsize=8.5)
b.axhline(90, color=INK2, ls='--', lw=1); b.text(1.42, 91.5, '90% target', ha='right', fontsize=8.5, color=INK2)
b.set_ylim(0, 105); b.set_ylabel('Registry coverage, same-trial test (%)'); b.grid(axis='y', color=GRID)
b.set_title('B. A wrong trial ID would have changed\nthe result; registry cross-check caught it', fontsize=11)

# C. consequence of unchecked automated PDF reading
c = fig.add_subplot(gs[0, 2])
vals = [med_real, max_real, pdf_gap]; cols = [BLUE, BLUE, ORANGE]
c.bar([0, 1, 2], vals, .55, color=cols)
for i, v in enumerate(vals): c.text(i, v + .06, f'{v:.2f} pp', ha='center', fontsize=10, color=INK)
c.set_xticks([0, 1, 2], ['Median real\nregistry-paper\ndifference', 'Largest real\nregistry-paper\ndifference', 'Automated reader:\ntwo values for one\nFDA herpes zoster RD'], fontsize=8.5)
c.set_ylabel('Difference in risk difference (percentage points)'); c.set_ylim(0, pdf_gap * 1.3); c.grid(axis='y', color=GRID)
c.set_title('C. One unchecked reading inconsistency\nexceeds every genuine report difference', fontsize=11)

# D. ledger: what the agent did autonomously, the guardrail, what it caught, the human checkpoint
d = fig.add_subplot(gs[1, :]); d.axis('off')
d.set_title('D. Session audit trail: autonomous steps, the guardrail on each, what it caught, and where a person decides', fontsize=11, loc='left')
cols = ['Step', 'Agent did (autonomously)', 'Guardrail', 'Caught / result', 'Human checkpoint']
W = [.11, .25, .21, .25, .16]
rows = [
 ['Retrieve registry', '5 trials via ClinicalTrials.gov API: 2,058 arm-level counts, 1,352 event pairs', 'Row and summed-count checksums against the live API', '5 of 5 trials matched exactly', 'None needed'],
 ['Identify trials', 'Mapped each NCT number to trial, drug, arms, doses', 'Cross-check NCT number against registry title and arms', '2 of 3 trial labels in the earlier dataset were wrong (BLISS-76; a 36-patient phase 2 study)', 'Confirm corrected IDs before use'],
 ['Read FDA review', 'Searched a 460,000-character review for per-trial AE tables', 'Cross-table consistency; match study numbers to arms', 'Pooled tables only; "Study 04/05" = TULIP-2/TULIP-1; two different herpes zoster counts (75/44 vs 28/6)', 'Verify the herpes zoster table on the PDF page'],
 ['Extract papers', 'Read 2 article tables (NEJM, PMC): 67 arm-level records', 'Every number stored with table locator and date; re-read against the page', f'{n_differ} of {n_pairs} pairs differ from the registry (median {med_real:.2f} pp)', 'Second, independent extractor'],
 ['Access', 'Tried the TULIP-1 article (ScienceDirect)', 'Never bypass paywalls or bot checks', '1 source blocked; earlier extraction flagged "re-verify"', 'Retrieve through the library'],
 ['Analyse', '6 scripts; 100-repeat splits; 10,000-draw randomization tests', 'Trial- and event-level splits; null model reported alongside ML', 'ML model about equal to the null model - reported, not hidden', 'Interpretation and claims'],
 ['Reproduce', 'Full rerun of the pipeline', 'Outputs compared byte for byte', '7 of 7 core output tables identical on rerun', 'None needed'],
]
x0 = 0; xs = np.cumsum([0] + W[:-1])
ytop, rh = .93, .128
for j, cname in enumerate(cols):
    d.add_patch(plt.Rectangle((xs[j], ytop), W[j] - .004, .065, color='#d9e1f2', transform=d.transAxes, clip_on=False))
    d.text(xs[j] + .006, ytop + .032, cname, transform=d.transAxes, fontsize=9.5, fontweight='bold', va='center', color=INK)
wrapw = [16, 44, 37, 44, 27]
for i, r in enumerate(rows):
    yy = ytop - (i + 1) * rh
    if i % 2 == 0:
        d.add_patch(plt.Rectangle((0, yy), 1, rh, color='#f4f3ef', transform=d.transAxes, clip_on=False))
    for j, v in enumerate(r):
        txt = '\n'.join(textwrap.wrap(v, wrapw[j]))
        col = ORANGE if (j == 3 and i in (1, 2, 4)) else INK
        d.text(xs[j] + .006, yy + rh / 2, txt, transform=d.transAxes, fontsize=8.6, va='center', color=col, fontweight='bold' if j == 0 else 'normal')
fig.suptitle('Why this study needs an agentic workflow - and why the agent needs guardrails', x=.06, ha='left', fontsize=14, fontweight='bold', color=INK)
fig.text(.06, .94, 'All numbers come from this project\'s files and the 2026-11-18 session log. Orange text in D = an error or trap that an unchecked pipeline would have carried into the analysis. '
         'Time savings and agent-vs-human accuracy are not shown: they will be measured during the fellowship.', fontsize=8.6, color=INK2, wrap=True)
fig.text(.06, .005, 'C: both herpes zoster values came from an automated reader of the FDA Saphnelo review (pooled 300 mg N=459 vs placebo N=466); which is correct must be checked on the PDF page. '
         'B: same-trial design, method A, 100 repeats.', fontsize=8, color=INK2)
fig.savefig('../figures/agentic_workflow_evidence.png', dpi=170)
print('saved', dict(reg=reg, pub=pub, cov_real=round(cov_real, 1), cov_mis=round(cov_mis, 1), pdf_gap=round(pdf_gap, 2), med=med_real, mx=max_real, n_differ=n_differ))
