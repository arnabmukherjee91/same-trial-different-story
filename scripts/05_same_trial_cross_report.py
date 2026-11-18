"""Same-trial, cross-report calibration test.

Question: does conformal prediction remain calibrated when a model trained and calibrated on one report
of a clinical trial (ClinicalTrials.gov) is applied to another report of the SAME trial (the journal article)?

Design (trial held fixed; only the report changes):
  * Unit = event = (trial, MedDRA term, active arm, seriousness). Registry and paper versions of one event
    always share a fold, so a test event's paper value never has its registry twin in training.
  * Events of all five trials are split at random into 5 folds (repeated R times). For fold k: test = k,
    calibration = k+1, training = the rest. Training and calibration use ClinicalTrials.gov records only,
    so the trial's own registry report is used to train and calibrate, and its paper report is only tested.
  * Coverage is measured three ways on the test fold:
      (1) all registry test events                          -> conformal guarantee applies (~90%)
      (2) registry values of events the paper also reports  -> effect of WHICH events the paper reports
      (3) paper values of those same events                 -> effect of the paper's numbers being different
  * Methods: A = one margin for all events; B = separate margins for serious / non-serious (Mondrian).
  * Also records, for each matched test event, the slack (margin - |registry residual|) and the
    registry-paper difference, to show how much disagreement it would take to flip coverage.
"""
import pandas as pd, numpy as np, sys, warnings, time
warnings.filterwarnings('ignore')
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from scipy.stats import beta

ALPHA = 0.10
R = int(sys.argv[1]) if len(sys.argv) > 1 else 20
X = pd.read_csv('../build/pairs_all_sources.csv')
KEY = ['nct_id', 'term', 'arm', 'event_type']
C = X[X.source.eq('ctgov')].reset_index(drop=True)
P = X[X.source.eq('publication')][KEY + ['rd']].rename(columns={'rd': 'rd_pub'})
C = C.merge(P, on=KEY, how='left')
C['matched'] = C.rd_pub.notna()
CAT = ['drug', 'route', 'dose', 'event_type', 'soc', 'phase']
NUM = ['fu', 'n1', 'n0']
F = CAT + NUM + ['term']


def model():
    pre = ColumnTransformer([('c', OneHotEncoder(handle_unknown='ignore'), CAT), ('n', StandardScaler(), NUM), ('t', TfidfVectorizer(), 'term')])
    return Pipeline([('p', pre), ('g', GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.05, random_state=0))])


def qhat(s, a=ALPHA):
    s = np.sort(np.asarray(s)); n = len(s); k = int(np.ceil((n + 1) * (1 - a)))
    return np.inf if k > n else s[k - 1]


rows = []
t0 = time.time()
for rep in range(R):
    rng = np.random.default_rng(1000 + rep)
    fold = rng.integers(0, 5, len(C))          # one row per event in C, so this is an event-level split
    for k in range(5):
        te, ca = fold == k, fold == (k + 1) % 5
        tr = ~(te | ca)
        for mname in ['GBM', 'Null (RD=0)']:
            if mname == 'GBM':
                m = model().fit(C.loc[tr, F], C.loc[tr, 'rd'])
                pc, pt = m.predict(C.loc[ca, F]), m.predict(C.loc[te, F])
            else:
                pc, pt = np.zeros(ca.sum()), np.zeros(te.sum())
            rc = np.abs(C.loc[ca, 'rd'].values - pc)
            T = C.loc[te].copy(); T['pred'] = pt
            qA = qhat(rc)
            qB = {e: qhat(rc[C.loc[ca, 'event_type'].values == e]) for e in ['Serious', 'Non-Serious']}
            for meth, q in [('A. one margin', np.full(len(T), qA)), ('B. Mondrian by seriousness', T.event_type.map(qB).values)]:
                T['q'] = q
                T['cov_ct'] = np.abs(T.rd - T.pred) <= T.q
                T['cov_pub'] = np.abs(T.rd_pub - T.pred) <= T.q
                for trial, g in list(T.groupby('trial')) + [('All trials', T)]:
                    mg = g[g.matched]
                    rows.append(dict(rep=rep, fold=k, model=mname, method=meth, trial=trial,
                                     n_all=len(g), cov_all_ct=g.cov_ct.sum(),
                                     n_matched=len(mg), cov_matched_ct=mg.cov_ct.sum(), cov_matched_pub=mg.cov_pub.sum(),
                                     n_matched_common=int((mg.event_type == 'Non-Serious').sum()),
                                     cov_matched_common_ct=int(mg[mg.event_type == 'Non-Serious'].cov_ct.sum()),
                                     cov_matched_common_pub=int(mg[mg.event_type == 'Non-Serious'].cov_pub.sum()),
                                     width_sum_all=2 * g.q.replace(np.inf, np.nan).sum(), width_sum_matched=2 * mg.q.replace(np.inf, np.nan).sum()))
                if mname == 'GBM' and meth.startswith('A'):
                    mg = T[T.matched]
                    for r in mg.itertuples():
                        rows.append(dict(rep=rep, fold=k, model='pairs', method=meth, trial=r.trial, term=r.term, arm=r.arm, event_type=r.event_type,
                                         rd_ct=r.rd, rd_pub=r.rd_pub, pred=r.pred, q=r.q, cov_ct=r.cov_ct, cov_pub=r.cov_pub))
    print(f'rep {rep + 1}/{R} done, {time.time() - t0:.0f}s', flush=True)

D = pd.DataFrame(rows)
D[D.model.eq('pairs')].dropna(axis=1, how='all').to_csv('../build/same_trial_pair_level.csv', index=False)
S = D[~D.model.eq('pairs')].dropna(axis=1, how='all')
S.to_csv('../build/same_trial_fold_level.csv', index=False)


def cp(k, n):
    return (beta.ppf(.025, k, n - k + 1) if k > 0 else 0.0, beta.ppf(.975, k + 1, n - k) if k < n else 1.0)


out = []
for (mname, meth, trial), g in S.groupby(['model', 'method', 'trial']):
    na, nm, nc = g.n_all.sum(), g.n_matched.sum(), g.n_matched_common.sum()
    res = dict(model=mname, method=meth, trial=trial, repeats=R,
               cov_all_registry=g.cov_all_ct.sum() / na,
               cov_paper_events_registry_values=g.cov_matched_ct.sum() / nm if nm else np.nan,
               cov_paper_events_paper_values=g.cov_matched_pub.sum() / nm if nm else np.nan,
               cov_common_registry=g.cov_matched_common_ct.sum() / nc if nc else np.nan,
               cov_common_paper=g.cov_matched_common_pub.sum() / nc if nc else np.nan,
               mean_width_all_pp=100 * g.width_sum_all.sum() / na,
               mean_width_paper_events_pp=100 * g.width_sum_matched.sum() / nm if nm else np.nan,
               test_events_per_repeat_all=na / R, test_events_per_repeat_matched=nm / R)
    out.append(res)
O = pd.DataFrame(out)
O['selection_effect_pp'] = 100 * (O.cov_paper_events_registry_values - O.cov_all_registry)
O['value_effect_pp'] = 100 * (O.cov_paper_events_paper_values - O.cov_paper_events_registry_values)
O.to_csv('../results/same_trial_cross_report_summary.csv', index=False)
pd.set_option('display.width', 250)
print(O.round(3).to_string(index=False))

# discordance at pair level (method A, GBM)
Pp = D[D.model.eq('pairs')]
flip = Pp[Pp.cov_ct != Pp.cov_pub]
print(f'\nPair-level (GBM, method A): {len(Pp)} matched test predictions over {R} repeats; '
      f'{len(flip)} flips ({(flip.cov_ct & ~flip.cov_pub).sum()} covered on registry but missed on paper, '
      f'{(~flip.cov_ct & flip.cov_pub).sum()} the reverse)')
Pp = Pp.assign(slack=Pp.q - np.abs(Pp.rd_ct - Pp.pred), delta=np.abs(Pp.rd_pub - Pp.rd_ct))
print('median margin slack (pp) on covered registry values:', round(100 * Pp[Pp.cov_ct].slack.median(), 2),
      '| median registry-paper difference (pp):', round(100 * Pp.delta.median(), 2), '| max:', round(100 * Pp.delta.max(), 2))
