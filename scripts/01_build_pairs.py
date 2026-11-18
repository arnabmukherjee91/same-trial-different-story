"""Build trial-event pairs (risk difference vs placebo) from ClinicalTrials.gov and publication records.
Each row keeps source, citation/locator and retrieval date so every number traces to a document."""
import pandas as pd, numpy as np, os
D='../build'; os.makedirs(D,exist_ok=True)
TRIALS={ # nct: (trial, drug, route, phase, ctgov_followup_wk, ctgov_timeframe)
 'NCT02446912':('TULIP-1','anifrolumab','IV','3',60,'Baseline to end of trial (max 60 wk)'),
 'NCT02446899':('TULIP-2','anifrolumab','IV','3',60,'Day 1 to end of study (max 60 wk)'),
 'NCT00410384':('BLISS-76','belimumab','IV','3',80,'Up to 80 wk (to wk 76/exit or 8 wk post last dose)'),
 'NCT00424476':('BLISS-52','belimumab','IV','3',56,'Up to 56 wk'),
 'NCT02962960':('SC-phase2 (D3461C00008)','anifrolumab','SC','2',52,'52 wk'),
}
DOSE={'Anifrolumab 150 mg':'low','Anifrolumab 300 mg':'high','Belimumab 1 mg/kg':'low','Belimumab 10 mg/kg':'high',
      'Anifrolumab - Lower Dose':'low','Anifrolumab - Higher Dose':'high'}
PBO={'Placebo','Placebo Comparator'}
# --- ClinicalTrials.gov: one table for all 5 trials (API v2, retrieved 2026-11-18; checksums in AGENTS.md)
d=pd.read_csv('../data/registry_ctgov.csv')
d=d[['nct_id','event_type','system_organ_class','ae_term','arm','affected','at_risk']]
d['source']='ctgov'; d['locator']='CT.gov API v2 resultsSection.adverseEventsModule'; d['retrieved']='2026-11-18'
def pairs(df,src):
    out=[]
    for (nct,et,term),g in df.groupby(['nct_id','event_type','ae_term']):
        p=g[g.arm.isin(PBO)]
        if len(p)!=1: continue
        p=p.iloc[0]
        for _,a in g[~g.arm.isin(PBO)].iterrows():
            t=TRIALS[nct]
            out.append(dict(source=src,nct_id=nct,trial=t[0],drug=t[1],route=t[2],phase=t[3],fu=t[4],arm=a.arm,dose=DOSE[a.arm],
                event_type=et,soc=a.get('system_organ_class',None),term=term,a=a.affected,n1=a.at_risk,c=p.affected,n0=p.at_risk,
                rd=a.affected/a.at_risk-p.affected/p.at_risk,locator=a.get('locator',''),retrieved=a.get('retrieved','')))
    return pd.DataFrame(out)
C=pairs(d,'ctgov')
# --- publications
p=pd.read_csv('../data/articles.csv')
p['event_type']=np.where(p.count_scope.eq('serious AE'),'Serious','Non-Serious')  # pub common-AE tables map to CT.gov 'other' table category
p=p.rename(columns={'term':'ae_term'})
soc=d.drop_duplicates(['ae_term'])[['ae_term','system_organ_class']]
p=p.merge(soc,on='ae_term',how='left')
P=pairs(p,'publication')
P=P.merge(p.drop_duplicates(['nct_id','ae_term','arm'])[['nct_id','ae_term','arm','period','citation']].rename(columns={'ae_term':'term'}),on=['nct_id','term','arm'],how='left')
# CT.gov serious count for the same term (pub any-AE counts include serious events; CT.gov 'other' table does not)
S=d[d.event_type.eq('Serious')].groupby(['nct_id','ae_term','arm']).affected.sum().rename('ctgov_serious').reset_index()
X=pd.concat([C,P],ignore_index=True)
X.to_csv(f'{D}/pairs_all_sources.csv',index=False)
S.to_csv(f'{D}/ctgov_serious_counts.csv',index=False)
print(X.groupby(['source','trial']).size().unstack(0))
print('missing SOC in pub:',P.soc.isna().sum())
