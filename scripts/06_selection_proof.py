"""Test the claim: "within a trial, what breaks calibration is that the paper reports a different,
non-random set of events, not that its numbers differ."

Same design as 05 (event-level 5-fold split within trials, model trained + calibrated on ClinicalTrials.gov,
method A: one conformal margin, alpha = 0.10), repeated R times so that every registry event gets an
out-of-fold coverage rate.

Three pieces of evidence, one figure:
  A. Coverage by event frequency (max incidence across the two arms, from the registry). If frequency
     drives the drop, coverage falls with frequency, and paper-reported events are covered like other
     events of the same frequency.
  B. Where the paper's events sit: the frequency distribution of paper-reported vs other registry events.
  C. Randomization test. Null 1: random sets of 52 registry events with the same trial x seriousness mix
     as the paper's events. Null 2: random sets of 52 events the papers did NOT report, matched on
     seriousness x frequency bin (phase 3 trials only). If the paper's events were a random sample of the
     trial's events, their coverage would look like null 1. If frequency explains the gap, it looks like null 2.
"""
import pandas as pd, numpy as np, sys, warnings, json
warnings.filterwarnings('ignore')
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ALPHA, R, NDRAW = 0.10, int(sys.argv[1]) if len(sys.argv) > 1 else 40, 10000
X = pd.read_csv('../build/pairs_all_sources.csv')
KEY = ['nct_id', 'term', 'arm', 'event_type']
C = X[X.source.eq('ctgov')].reset_index(drop=True)
P = X[X.source.eq('publication')][KEY + ['rd']].rename(columns={'rd': 'rd_pub'})
C = C.merge(P, on=KEY, how='left')
C['reported'] = C.rd_pub.notna()
C['freq'] = np.maximum(C.a / C.n1, C.c / C.n0)
BINS = [-1, 0.02, 0.05, 0.10, 1.01]
LAB = ['<2%', '2-5%', '5-10%', '>=10%']
C['fbin'] = pd.cut(C.freq, BINS, labels=LAB)
CAT = ['drug', 'route', 'dose', 'event_type', 'soc', 'phase']; NUM = ['fu', 'n1', 'n0']; F = CAT + NUM + ['term']


def model():
    pre = ColumnTransformer([('c', OneHotEncoder(handle_unknown='ignore'), CAT), ('n', StandardScaler(), NUM), ('t', TfidfVectorizer(), 'term')])
    return Pipeline([('p', pre), ('g', GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.05, random_state=0))])


def qhat(s, a=ALPHA):
    s = np.sort(s); n = len(s); k = int(np.ceil((n + 1) * (1 - a))); return np.inf if k > n else s[k - 1]


cov_ct = np.zeros(len(C)); cov_pub = np.zeros(len(C))
for rep in range(R):
    fold = np.random.default_rng(1000 + rep).integers(0, 5, len(C))
    for k in range(5):
        te, ca = fold == k, fold == (k + 1) % 5; tr = ~(te | ca)
        m = model().fit(C.loc[tr, F], C.loc[tr, 'rd'])
        q = qhat(np.abs(C.loc[ca, 'rd'].values - m.predict(C.loc[ca, F])))
        pt = m.predict(C.loc[te, F])
        cov_ct[te] += np.abs(C.loc[te, 'rd'].values - pt) <= q
        cov_pub[te] += np.abs(C.loc[te, 'rd_pub'].values - pt) <= q
    print(f'rep {rep + 1}/{R}', flush=True)
C['cov_ct'] = cov_ct / R; C['cov_pub'] = np.where(C.reported, cov_pub / R, np.nan)
C.drop(columns=['locator', 'retrieved', 'period', 'citation']).to_csv('../build/selection_event_coverage.csv', index=False)

Rp = C[C.reported]
obs_ct, obs_pub, all_ct = Rp.cov_ct.mean(), Rp.cov_pub.mean(), C.cov_ct.mean()
rng = np.random.default_rng(7)
# Null 1: same trial x seriousness mix, drawn from all registry events of those trials
need1 = Rp.groupby(['trial', 'event_type']).size()
pools1 = {k: C[(C.trial == k[0]) & (C.event_type == k[1])].cov_ct.values for k in need1.index}
null1 = np.array([np.concatenate([rng.choice(pools1[k], n, replace=False) for k, n in need1.items()]).mean() for _ in range(NDRAW)])
# Null 2: same seriousness x frequency-bin mix, drawn from events NO paper reported (phase 3 trials)
need2 = Rp.groupby(['event_type', 'fbin'], observed=True).size()
pool_base = C[~C.reported & C.phase.astype(str).eq('3')]
pools2 = {k: pool_base[(pool_base.event_type == k[0]) & (pool_base.fbin == k[1])].cov_ct.values for k in need2.index}
null2 = np.array([np.concatenate([rng.choice(pools2[k], n, replace=len(pools2[k]) < n) for k, n in need2.items()]).mean() for _ in range(NDRAW)])
p1 = (np.sum(null1 <= obs_ct) + 1) / (NDRAW + 1)
p2_two = (np.sum(np.abs(null2 - null2.mean()) >= abs(obs_ct - null2.mean())) + 1) / (NDRAW + 1)
by_bin = C.groupby('fbin', observed=True).agg(n_all=('cov_ct', 'size'), cov_all=('cov_ct', 'mean'))
by_bin = by_bin.join(Rp.groupby('fbin', observed=True).agg(n_paper=('cov_ct', 'size'), cov_paper_registry=('cov_ct', 'mean'), cov_paper_paper=('cov_pub', 'mean')))
by_bin = by_bin.join(C[~C.reported & C.phase.astype(str).eq('3')].groupby('fbin', observed=True).agg(n_unreported_ph3=('cov_ct', 'size'), cov_unreported_ph3=('cov_ct', 'mean')))
by_bin.to_csv('../results/selection_coverage_by_frequency.csv')
stats = dict(repeats=R, draws=NDRAW, n_registry_events=len(C), n_paper_events=len(Rp),
             coverage_all_registry=round(all_ct, 4), coverage_paper_events_registry_values=round(obs_ct, 4),
             coverage_paper_events_paper_values=round(obs_pub, 4),
             null1_mean=round(null1.mean(), 4), null1_2p5=round(np.quantile(null1, .025), 4), null1_97p5=round(np.quantile(null1, .975), 4), p_null1_one_sided=round(p1, 5),
             null2_mean=round(null2.mean(), 4), null2_2p5=round(np.quantile(null2, .025), 4), null2_97p5=round(np.quantile(null2, .975), 4), p_null2_two_sided=round(p2_two, 4),
             pct_paper_events_freq_ge5=round(100 * (Rp.freq >= .05).mean(), 1), pct_other_events_freq_ge5=round(100 * (C[~C.reported].freq >= .05).mean(), 1),
             null2_pools_with_replacement=[f'{k}: pool {len(pools2[k])} < need {n}' for k, n in need2.items() if len(pools2[k]) < n])
json.dump(stats, open('../results/selection_test_stats.json', 'w'), indent=1)
print(json.dumps(stats, indent=1)); print(by_bin.round(3))

# ---------------- figure ----------------
BLUE, ORANGE, AQUA, INK, INK2, GRID = '#2a78d6', '#eb6834', '#1baf7a', '#0b0b0b', '#52514e', '#e6e5e0'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.titleweight': 'bold', 'axes.titlesize': 11, 'axes.titlelocation': 'left'})
fig, ax = plt.subplots(1, 3, figsize=(15, 4.9), gridspec_kw=dict(width_ratios=[1.15, 1, 1.25]))
fig.patch.set_facecolor('white')
# A: coverage vs frequency
a = ax[0]; xs = np.arange(len(LAB)); w = .36
a.bar(xs - w / 2, 100 * by_bin.cov_all, w, color=BLUE, label='All registry event pairs', zorder=3)
a.bar(xs + w / 2, 100 * by_bin.cov_paper_registry.fillna(0), w, color=ORANGE, label='Article-reported event pairs', zorder=3)
a.axhline(90, color=INK2, lw=1, ls='--', zorder=2); a.text(len(LAB) - .45, 86, 'nominal 90%', ha='right', color=INK2, fontsize=9)
for i, r in enumerate(by_bin.itertuples()):
    a.text(i - w / 2, 2, f'n={r.n_all}', ha='center', va='bottom', fontsize=8, color='white', zorder=4)
    if r.n_paper == r.n_paper and r.n_paper > 0:
        a.text(i + w / 2, 2, f'n={int(r.n_paper)}', ha='center', va='bottom', fontsize=8, color='white', zorder=4)
a.set_xticks(xs, LAB); a.set_xlabel('Event frequency (higher arm incidence, registry)'); a.set_ylabel('Coverage of 90% interval (%)')
a.set_ylim(0, 118); a.set_yticks([0,20,40,60,80,100]); a.grid(axis='y', color=GRID, zorder=0); a.legend(frameon=False, loc='upper center', ncol=2, fontsize=9)
a.set_title('A. Coverage by event frequency')
# B: where events sit
b = ax[1]
for lab, sel, col in [('Not reported', ~C.reported, BLUE), ('Reported', C.reported, ORANGE)]:
    v = np.sort(100 * C.loc[sel, 'freq'].values); b.step(v, np.arange(1, len(v) + 1) / len(v) * 100, where='post', color=col, lw=2, label=f'{lab} (n={len(v)})')
for t in (5, 10):
    b.axvline(t, color=INK2, lw=1, ls=':'); b.text(t + .4, 4, f'{t}%', color=INK2, fontsize=9)
b.set_xscale('symlog', linthresh=1); b.set_xlim(0, 60); b.set_xticks([0, 1, 2, 5, 10, 20, 50], ['0', '1', '2', '5', '10', '20', '50'])
b.set_xlabel('Event frequency, % (log scale)'); b.set_ylabel('Cumulative share of events (%)'); b.grid(color=GRID)
b.legend(frameon=False, loc='upper left', fontsize=9)
b.set_title(f'B. Event frequency distribution\n(>=5%: {stats["pct_paper_events_freq_ge5"]:.0f}% reported vs {stats["pct_other_events_freq_ge5"]:.0f}% not reported)', fontsize=11)
# C: randomization test
c = ax[2]; bins = np.linspace(.55, 1.05, 51)
c.hist(100 * null1, bins=100 * bins, color=BLUE, alpha=.85, label='Null 1: matched on trial\nand seriousness')
c.hist(100 * null2, bins=100 * bins, color=AQUA, alpha=.85, label='Null 2: unreported pairs,\nmatched on frequency\nand seriousness')
c.axvline(100 * obs_ct, color=ORANGE, lw=2.5); c.axvline(100 * obs_pub, color=ORANGE, lw=1.5, ls='--')
c.text(91, c.get_ylim()[1] * .97, f'Observed (52 pairs)\nregistry RD: {100 * obs_ct:.1f}%\narticle RD: {100 * obs_pub:.1f}% (dashed)', ha='left', va='top', fontsize=9, color=INK)
c.set_xlabel('Coverage, 52 event pairs (%)'); c.set_ylabel(f'Count of {NDRAW:,} random draws'); c.grid(axis='y', color=GRID)
c.legend(frameon=False, loc='center right', bbox_to_anchor=(1.0, .45), fontsize=8.5); c.set_xlim(52, 122); c.set_xticks([60,70,80,90,100])
c.set_title(f'C. Randomization test, {NDRAW:,} draws\n(null 1: p = {p1:.3f}; null 2: p = {p2_two:.2f})', fontsize=11)
fig.suptitle('Coverage of registry-calibrated 90% conformal intervals on article-reported event pairs',
             x=.01, ha='left', fontsize=12, fontweight='bold', color=INK)
fig.text(.01, .005, f'Model trained and calibrated on ClinicalTrials.gov, event-level 5-fold split within trials, {R} repeats, one conformal margin (alpha=0.10). '
         f'Paper events: 52 from TULIP-1, TULIP-2, BLISS-76. All registry events: {len(C)} from 5 trials. Null 2 pool: phase 3 trials only.', fontsize=8, color=INK2)
fig.tight_layout(rect=(0, .03, 1, .93), w_pad=3)
fig.savefig('../figures/selection_proof.png', dpi=170)
print('saved')
