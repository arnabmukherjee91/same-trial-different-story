"""Cross-source calibration test.
Question: an interval built from ClinicalTrials.gov records of OTHER trials - does it still cover the
risk difference that a different report (the journal publication) gives for the SAME held-out trial?
All splits are at trial level. Model never sees counts, rates, or the source label."""
import pandas as pd, numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from scipy.stats import beta
ALPHA=0.10
X=pd.read_csv('../build/pairs_all_sources.csv')
C=X[X.source.eq('ctgov')].reset_index(drop=True); P=X[X.source.eq('publication')].reset_index(drop=True)
CAT=['drug','route','dose','event_type','soc','phase']; NUM=['fu','n1','n0']
def model():
    pre=ColumnTransformer([('c',OneHotEncoder(handle_unknown='ignore'),CAT),('n',StandardScaler(),NUM),('t',TfidfVectorizer(),'term')])
    return Pipeline([('p',pre),('g',GradientBoostingRegressor(n_estimators=300,max_depth=3,learning_rate=0.05,random_state=0))])
class Null:  # baseline: predicts no drug effect
    def fit(self,*a): return self
    def predict(self,Z): return np.zeros(len(Z))
def qhat(s,a=ALPHA):
    s=np.sort(np.asarray(s)); n=len(s); k=int(np.ceil((n+1)*(1-a)))
    return np.inf if k>n else s[k-1]
def cp(k,n):  # Clopper-Pearson 95%
    lo=beta.ppf(.025,k,n-k+1) if k>0 else 0; hi=beta.ppf(.975,k+1,n-k) if k<n else 1; return lo,hi
F=CAT+NUM+['term']
trials=sorted(C.trial.unique()); published=sorted(P.trial.unique())
rows=[]; detail=[]
for T in published:
    pool=[t for t in trials if t!=T]
    te_c=C[C.trial.eq(T)]; te_p=P[P.trial.eq(T)]
    key=['term','arm','event_type']
    m=te_c.rename(columns={'rd':'rd_ct','a':'a_ct','c':'c_ct'}).merge(te_p[key+['rd','a','c','n1','n0']].rename(columns={'rd':'rd_pub','a':'a_pub','c':'c_pub','n1':'n1_pub','n0':'n0_pub'}),on=key)  # matched pairs (both sources report)
    for mname,M in [('GBM',model),('Null (RD=0)',Null)]:
        # leave-one-trial-out residuals inside the non-test pool (used by CV+, Mondrian and source-conditional)
        loto={}
        for j in pool:
            mj=M().fit(C[C.trial.isin([t for t in pool if t!=j])][F],C[C.trial.isin([t for t in pool if t!=j])].rd)
            loto[j]=mj
        res_ct=pd.concat([C[C.trial.eq(j)].assign(r=lambda z,j=j: np.abs(z.rd-loto[j].predict(z[F]))) for j in pool])
        res_pub=pd.concat([P[P.trial.eq(j)].assign(r=lambda z,j=j: np.abs(z.rd-loto[j].predict(z[F]))) for j in pool if j in published])
        full=M().fit(C[C.trial.isin(pool)][F],C[C.trial.isin(pool)].rd)
        pred=full.predict(m[F])
        methods={
          'A. CV+ by trial (CT.gov calib, all events)': np.full(len(m),qhat(res_ct.r)),
          'B. Mondrian by seriousness (CT.gov calib)': np.array([qhat(res_ct[res_ct.event_type.eq(e)].r) for e in m.event_type]),
          'C. Source-conditional (publication calib of other trials)': np.array([qhat(res_pub[res_pub.event_type.eq(e)].r) if (res_pub.event_type.eq(e)).sum()>=9 else np.inf for e in m.event_type]),
        }
        # split conformal: calibrate on ONE other trial, train on the rest (rotated) -> shows instability with few trials
        for j in pool:
            mj=loto[j]; q=qhat(np.abs(C[C.trial.eq(j)].rd-mj.predict(C[C.trial.eq(j)][F])))
            pr=mj.predict(m[F]); w=np.full(len(m),q)
            for s in ['ct','pub']:
                cov=np.abs(m[f'rd_{s}']-pr)<=w; k=int(cov.sum()); n=len(m)
                rows.append(dict(test_trial=T,model=mname,method=f'D. Split (calib = {j} only)',target_source={'ct':'CT.gov','pub':'Publication'}[s],
                                 n_pairs=n,covered=k,coverage=k/n,ci_lo=cp(k,n)[0],ci_hi=cp(k,n)[1],width_pp=200*np.median(w)))
        for meth,q in methods.items():
            for s in ['ct','pub']:
                cov=np.abs(m[f'rd_{s}']-pred)<=q; k=int(cov.sum()); n=len(m)
                rows.append(dict(test_trial=T,model=mname,method=meth,target_source={'ct':'CT.gov','pub':'Publication'}[s],
                                 n_pairs=n,covered=k,coverage=k/n,ci_lo=cp(k,n)[0],ci_hi=cp(k,n)[1],width_pp=200*np.median(q) if np.isfinite(q).all() else np.inf))
            if mname=='GBM':
                detail.append(m.assign(method=meth,pred=pred,half_width=q,
                    cov_ct=np.abs(m.rd_ct-pred)<=q,cov_pub=np.abs(m.rd_pub-pred)<=q))
        # coverage on ALL CT.gov records of the test trial (not just those the paper reports) for method A
        if True:
            qa=qhat(res_ct.r); k=int((np.abs(te_c.rd-full.predict(te_c[F]))<=qa).sum()); n=len(te_c)
            rows.append(dict(test_trial=T,model=mname,method='A. CV+ by trial (CT.gov calib, all events)',target_source='CT.gov (all records)',
                             n_pairs=n,covered=k,coverage=k/n,ci_lo=cp(k,n)[0],ci_hi=cp(k,n)[1],width_pp=200*qa))
R=pd.DataFrame(rows); R.to_csv('../results/coverage_by_trial_source_method.csv',index=False)
Dt=pd.concat(detail); Dt.to_csv('../build/pair_level_predictions.csv',index=False)
pd.set_option('display.width',250); pd.set_option('display.max_colwidth',60)
print(R[R.model.eq('GBM')&~R.method.str.startswith('D')].round(3).to_string(index=False))
print('\nSplit conformal with a single calibration trial (GBM):')
print(R[R.model.eq('GBM')&R.method.str.startswith('D')][['test_trial','method','target_source','covered','n_pairs','width_pp']].round(2).to_string(index=False))
print('\nNull model, method A/B:')
print(R[R.model.str.startswith('Null')&R.method.str[:1].isin(['A','B'])][['test_trial','method','target_source','covered','n_pairs','width_pp']].round(2).to_string(index=False))
