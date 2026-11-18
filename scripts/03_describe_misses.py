"""Descriptive analysis: where CT.gov and publication disagree, and whether interval misses coincide with
differences in counts, denominators, follow-up windows, event definitions (seriousness split) or omissions."""
import pandas as pd, numpy as np
from scipy.stats import beta
X=pd.read_csv('../build/pairs_all_sources.csv'); S=pd.read_csv('../build/ctgov_serious_counts.csv')
D=pd.read_csv('../build/pair_level_predictions.csv')
PERIOD={'TULIP-1':('CT.gov max 60 wk','pub 52-wk treatment period (to verify)'),'TULIP-2':('CT.gov max 60 wk','pub 52-wk intervention period'),
        'BLISS-76':('CT.gov up to 80 wk (incl. 8 wk post-dose)','pub through wk 76')}
def cp(k,n):
    return (beta.ppf(.025,k,n-k+1) if k>0 else 0, beta.ppf(.975,k+1,n-k) if k<n else 1)
# 1. coverage by event category (primary = common AEs, non-serious category)
rows=[]
for (t,meth,et),g in D.groupby(['trial','method','event_type']):
    for s in ['ct','pub']:
        k=int(g[f'cov_{s}'].sum()); n=len(g); lo,hi=cp(k,n)
        rows.append(dict(test_trial=t,method=meth,event_category='common AE (any/non-serious)' if et=='Non-Serious' else 'serious AE',
            target_source='CT.gov' if s=='ct' else 'Publication',covered=k,n_pairs=n,coverage=round(k/n,3),ci95=f'{lo:.2f}-{hi:.2f}',
            median_width_pp=round(200*np.median(g.half_width),1) if np.isfinite(g.half_width).all() else 'inf (no calibration records)'))
cov=pd.DataFrame(rows); cov.to_csv('../build/coverage_by_event_category.csv',index=False)
# 2. source differences per matched pair (method A rows only, one per pair)
A=D[D.method.str.startswith('A.')].copy()
A=A.merge(S.rename(columns={'ae_term':'term','ctgov_serious':'ser_a'}).merge(pd.read_csv('../build/pairs_all_sources.csv')[['nct_id','trial']].drop_duplicates(),on='nct_id')[['trial','term','arm','ser_a']],on=['trial','term','arm'],how='left')
pbo=S[S.arm.str.contains('Placebo')].rename(columns={'ae_term':'term','ctgov_serious':'ser_c'})
A=A.merge(pbo.merge(X[['nct_id','trial']].drop_duplicates(),on='nct_id')[['trial','term','ser_c']],on=['trial','term'],how='left')
A[['ser_a','ser_c']]=A[['ser_a','ser_c']].fillna(0)
A['abs_rd_diff_pp']=100*np.abs(A.rd_ct-A.rd_pub)
A['count_diff_active']=A.a_pub-A.a_ct; A['count_diff_placebo']=A.c_pub-A.c_ct
A['denominator_differs']=(A.n1!=A.n1_pub)|(A.n0!=A.n0_pub)
A['window_differs']=True  # all three trials: CT.gov window extends past the publication's analysis period
A['definition_split']=(A.event_type.eq('Non-Serious'))&((A.ser_a>0)|(A.ser_c>0))  # pub any-AE vs CT.gov non-serious table, term also has serious events
def reason(r):
    rs=[]
    if r.count_diff_active==0 and r.count_diff_placebo==0: return 'identical counts'
    if r.denominator_differs: rs.append('denominator')
    if r.definition_split: rs.append('seriousness split (term also in CT.gov serious table)')
    if r.trial in PERIOD: rs.append('follow-up window')
    return '; '.join(rs) if rs else 'unexplained count difference'
A['candidate_explanations']=A.apply(reason,axis=1)
A['discordant']=A.cov_ct!=A.cov_pub
A['ctgov_window'],A['pub_window']=zip(*A.trial.map(PERIOD))
cols=['trial','arm','term','event_type','a_ct','n1','c_ct','n0','a_pub','n1_pub','c_pub','n0_pub','ser_a','ser_c','rd_ct','rd_pub','abs_rd_diff_pp','pred','half_width','cov_ct','cov_pub','discordant','candidate_explanations','ctgov_window','pub_window']
A[cols].round(4).to_csv('../results/source_differences_and_misses.csv',index=False)
# 3. omissions: CT.gov 'other' (non-serious) pairs absent from the publication table, and vice versa
C=X[X.source.eq('ctgov')&X.event_type.eq('Non-Serious')]; P=X[X.source.eq('publication')]
om=[]
for t in P.trial.unique():
    ct=set(zip(C[C.trial.eq(t)].term,C[C.trial.eq(t)].arm)); pb=set(zip(P[P.trial.eq(t)&P.event_type.eq('Non-Serious')].term,P[P.trial.eq(t)&P.event_type.eq('Non-Serious')].arm))
    om.append(dict(trial=t,ctgov_common_pairs=len(ct),pub_common_pairs=len(pb),in_both=len(ct&pb),ctgov_only=len(ct-pb),pub_only=len(pb-ct),
                   ctgov_only_terms='; '.join(sorted({x[0] for x in ct-pb})),pub_only_terms='; '.join(sorted({x[0] for x in pb-ct}))))
om=pd.DataFrame(om); om.to_csv('../build/omissions_by_trial.csv',index=False)
pd.set_option('display.width',250); pd.set_option('display.max_colwidth',90)
print(cov.to_string(index=False)); print()
print(om.to_string(index=False)); print()
print('Median |RD_ct - RD_pub| (pp) by trial:'); print(A.groupby('trial').abs_rd_diff_pp.agg(['median','max','count']).round(2))
print('\nPairs with identical counts:',(A.candidate_explanations=='identical counts').sum(),'of',len(A))
print('\nDiscordant pairs (method A):'); print(A[A.discordant][['trial','arm','term','rd_ct','rd_pub','pred','half_width','cov_ct','cov_pub','candidate_explanations']].round(3).to_string(index=False))
print('\nAll misses on publication (method A):'); print(A[~A.cov_pub][['trial','arm','term','rd_ct','rd_pub','pred','half_width','cov_ct','candidate_explanations']].round(3).to_string(index=False))
