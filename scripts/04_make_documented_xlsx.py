"""Write a documented .xlsx next to every data table (CSV, and the two raw CT.gov text pulls).
Sheet 'About' = what the table is, what a row is, how it was obtained, column dictionary.
Sheet 'Data'  = the table itself; each header cell carries its column meaning as a comment.
CSV files are left untouched (the analysis scripts read them). Run from the scripts/ folder."""
import pandas as pd, numpy as np, os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter

ROOT = '..'
CTGOV_URL = 'https://clinicaltrials.gov/api/v2/studies/<NCT>?fields=resultsSection.adverseEventsModule'
TRIALS_TXT = ('TULIP-1 = NCT02446912 (anifrolumab IV 150/300 mg vs placebo); TULIP-2 = NCT02446899 (anifrolumab IV 300 mg); '
              'BLISS-76 = NCT00410384 (belimumab IV 1/10 mg/kg); BLISS-52 = NCT00424476 (belimumab IV 1/10 mg/kg); '
              'SC-phase2 (D3461C00008) = NCT02962960 (anifrolumab subcutaneous, phase 2, n=36).')

# ---------- shared column meanings: (meaning, units/values, where it comes from) ----------
C = {
 'source': ('Which report the row comes from', 'ctgov = ClinicalTrials.gov results record; publication = journal article', 'Set by 01_build_pairs.py'),
 'nct_id': ('ClinicalTrials.gov registry number of the trial', 'e.g. NCT02446899', 'Registry'),
 'trial': ('Trial short name', 'TULIP-1, TULIP-2, BLISS-76, BLISS-52, SC-phase2 (D3461C00008)', 'Mapped from nct_id (see Trials above)'),
 'drug': ('Study drug', 'anifrolumab / belimumab', 'Trial design (registry)'),
 'route': ('Route of administration', 'IV = intravenous, SC = subcutaneous', 'Trial design (registry)'),
 'phase': ('Trial phase', '2 or 3', 'Registry'),
 'fu': ('Follow-up window for adverse events in the CT.gov record', 'weeks', 'CT.gov AE time frame (TULIP-1/2 60, BLISS-76 80, BLISS-52 56, SC 52)'),
 'arm': ('Active treatment arm compared with placebo', 'arm label as written in CT.gov', 'Registry / publication'),
 'dose': ('Dose level of the active arm', 'low (anifrolumab 150 mg; belimumab 1 mg/kg; SC lower) / high (anifrolumab 300 mg; belimumab 10 mg/kg; SC higher)', 'Coded by us from the arm label'),
 'event_type': ('Seriousness category', 'Serious / Non-Serious. Publication "any AE" tables are coded Non-Serious to match the CT.gov "other (non-serious) AE" table', 'CT.gov table the event is listed in; for publications, the table section'),
 'soc': ('MedDRA System Organ Class', 'text', 'CT.gov; for publication rows copied from the CT.gov row with the same term'),
 'term': ('MedDRA Preferred Term of the adverse event', 'text (publication spellings harmonised to MedDRA, e.g. Diarrhea -> Diarrhoea)', 'CT.gov / publication table'),
 'ae_term': ('MedDRA Preferred Term of the adverse event', 'text', 'CT.gov'),
 'a': ('Participants WITH the event in the active arm', 'count', 'Source table'),
 'n1': ('Participants AT RISK in the active arm (CT.gov denominator)', 'count', 'Source table'),
 'c': ('Participants WITH the event in the placebo arm', 'count', 'Source table'),
 'n0': ('Participants AT RISK in the placebo arm (CT.gov denominator)', 'count', 'Source table'),
 'rd': ('Risk difference, active minus placebo', 'proportion: a/n1 - c/n0 (0.05 = 5 percentage points)', 'Calculated'),
 'locator': ('Where in the source document the number is', 'e.g. "Table 3"; CT.gov API module name', 'Recorded at extraction'),
 'retrieved': ('Date the source was accessed', 'YYYY-MM-DD', 'Recorded at extraction'),
 'period': ('Analysis period stated by the publication', 'text', 'Publication methods / table footnote'),
 'citation': ('Bibliographic citation of the source', 'text', 'Publication'),
 'a_ct': ('Participants with the event, active arm, per CT.gov', 'count', 'CT.gov'),
 'c_ct': ('Participants with the event, placebo arm, per CT.gov', 'count', 'CT.gov'),
 'rd_ct': ('Risk difference per CT.gov', 'proportion', 'Calculated from CT.gov counts'),
 'a_pub': ('Participants with the event, active arm, per publication', 'count', 'Publication table'),
 'c_pub': ('Participants with the event, placebo arm, per publication', 'count', 'Publication table'),
 'n1_pub': ('Participants at risk, active arm, per publication', 'count', 'Publication table header N'),
 'n0_pub': ('Participants at risk, placebo arm, per publication', 'count', 'Publication table header N'),
 'rd_pub': ('Risk difference per publication', 'proportion', 'Calculated from publication counts'),
 'method': ('Conformal method used to build the interval', 'A = CV+ by trial; B = Mondrian by seriousness; C = source-conditional (publication calibration); D = split with one calibration trial', '02_cross_source_conformal.py'),
 'model': ('Point-prediction model', 'GBM = gradient boosting regressor; Null (RD=0) = predicts no drug effect (baseline)', '02_cross_source_conformal.py'),
 'pred': ('Model-predicted risk difference', 'proportion', 'GBM trained on CT.gov records of all non-test trials'),
 'half_width': ('Half-width of the 90% conformal interval', 'proportion; interval = pred +/- half_width; inf = no calibration records', 'Conformal quantile of calibration residuals'),
 'cov_ct': ('Did the interval contain the CT.gov risk difference?', 'TRUE / FALSE', '|rd_ct - pred| <= half_width'),
 'cov_pub': ('Did the interval contain the publication risk difference?', 'TRUE / FALSE', '|rd_pub - pred| <= half_width'),
 'test_trial': ('Held-out trial whose records are being predicted', 'trial name', 'Leave-one-trial-out design'),
 'target_source': ('Which report coverage is measured against', 'CT.gov; Publication; CT.gov (all records) = every CT.gov pair of the test trial, not only those the paper also reports', '02 script'),
 'n_pairs': ('Number of trial-event pairs evaluated', 'count', '02/03 script'),
 'covered': ('How many of those pairs fell inside their interval', 'count', '02/03 script'),
 'coverage': ('Share of pairs covered', 'fraction (target 0.90)', 'covered / n_pairs'),
 'ci_lo': ('Lower 95% Clopper-Pearson bound for coverage', 'fraction', 'Exact binomial CI'),
 'ci_hi': ('Upper 95% Clopper-Pearson bound for coverage', 'fraction', 'Exact binomial CI'),
 'ci95': ('95% Clopper-Pearson interval for coverage', '"lower-upper"', 'Exact binomial CI'),
 'width_pp': ('Median full interval width', 'percentage points (2 x half_width x 100); inf = unbounded', '02 script'),
 'median_width_pp': ('Median full interval width', 'percentage points; "inf" = no calibration records for that category', '03 script'),
 'event_category': ('Event group', 'common AE (any/non-serious) or serious AE', 'From event_type'),
 'ctgov_serious': ('Participants with this term in the CT.gov SERIOUS AE table', 'count', 'CT.gov serious events, summed per trial x term x arm'),
}

HOW_CT = ('ClinicalTrials.gov results were downloaded from the public API v2 (resultsSection.adverseEventsModule) on 2026-11-18 '
          'through the built-in browser (the analysis computer cannot reach clinicaltrials.gov directly). Row counts and summed participant counts per trial '
          'were checked against the live API: TULIP-1 160 terms/1092, TULIP-2 60/425, BLISS-76 246/2565, BLISS-52 165/1972, NCT02962960 75/111 - all matched. '
          'TULIP-1, BLISS-76 and NCT02962960 come from an earlier pull, verified identical to the API on 2026-11-18 (its trial labels were corrected - see the audit log in AGENTS.md); '
          'TULIP-2 and BLISS-52 were pulled on 2026-11-18. All five are combined in data/registry_ctgov.csv.')
HOW_PUB = ('Publication counts were read from the article tables: TULIP-2 = Morand et al., NEJM 2020;382:211-221, Table 3 (nejm.org full text, read 2026-11-18); '
           'BLISS-76 = Furie et al., Arthritis Rheum 2011;63:3918-30, Table 3 (PubMed Central PMC5007058, read 2026-11-18); '
           'TULIP-1 = Furie et al., Lancet Rheumatol 2019 - 6 terms carried over from the 2026-11-01 feasibility extraction '
           '(internal feasibility file), NOT yet re-verified (ScienceDirect blocked access with a bot check on 2026-11-18). '
           'TULIP-1 publication denominators were assumed equal to CT.gov (93/180/184) - to verify. Numbers were typed from the page and re-checked against it.')


def _raw(p, armcols):
    rows = []
    for l in open(p).read().strip().split('\n'):
        k, term, soc, cnt = l.split('|')
        rows.append([k, term, soc] + cnt.split(';'))
    return pd.DataFrame(rows, columns=['table', 'term', 'soc'] + armcols)


def pick(keys):
    return {k: C[k] for k in keys}


DOCS = {
 'data/registry_ctgov.csv': dict(
   title='ClinicalTrials.gov adverse-event results, all 5 trials (one row per term x seriousness table x arm)',
   row='One adverse-event term, in one CT.gov table (Serious or Other/non-serious), for one arm.',
   how=HOW_CT,
   script='Pulled from the API (browser JavaScript over the JSON); verify against the live API with scripts/00_verify_ctgov.py',
   sources=CTGOV_URL.replace('<NCT>', '<NCT number>'),
   cols={'nct_id': C['nct_id'], 'trial': C['trial'],
         'event_type': ('CT.gov table the term is listed in', 'Serious = serious AE table; Non-Serious = "other" AE table (listed if >=5% in any arm)', 'CT.gov'),
         'system_organ_class': C['soc'], 'ae_term': C['ae_term'],
         'arm': ('Trial arm (active or placebo)', 'CT.gov arm label', 'CT.gov event group'),
         'affected': ('Participants with the event in this arm', 'count', 'CT.gov numAffected'),
         'at_risk': ('Participants at risk in this arm', 'count', 'CT.gov numAtRisk')},
   caveats='A participant can appear in both the serious and the non-serious table. AE time frames differ by trial (TULIP-1/2 60 wk, BLISS-76 80, BLISS-52 56, SC phase 2 52).'),
 'data/articles.csv': dict(
   title='Journal-article adverse-event counts, one row per arm (source-linked)',
   row='One adverse-event term x one arm (active or placebo) as printed in a journal article table.',
   how=HOW_PUB,
   script='Typed by hand from the article tables (TULIP-2, BLISS-76); TULIP-1 rows appended by a short Python step from the earlier feasibility file',
   sources='https://www.nejm.org/doi/full/10.1056/NEJMoa1912196 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC5007058/ ; https://doi.org/10.1016/S2665-9913(19)30076-1',
   cols={**pick(['nct_id', 'trial', 'source', 'citation', 'locator', 'retrieved', 'period', 'term']),
         'arm': ('Arm (active or placebo)', 'label harmonised to CT.gov arm names', 'Article table column'),
         'affected': ('Participants with the event in this arm', 'count', 'Article table n (%) - the n'),
         'at_risk': ('Participants at risk in this arm', 'count', 'Article table column header N'),
         'count_scope': ('What the article counted', 'any AE = all occurrences regardless of seriousness; serious AE = SAE section', 'Article table section'),
         'reported_threshold': ("Article's rule for which events are listed", 'e.g. >5% in anifrolumab arm (TULIP-2); >=10% of any group (BLISS-76)', 'Article table title / footnote')},
   caveats='Events below the article threshold are NOT zero - they are "not reported". TULIP-1 rows need re-verification.'),
 'data/fda_reviews.csv': dict(
   title='FDA review documents checked for trial-specific adverse-event counts',
   row='One FDA review document (one per drug).',
   how=('The FDA review PDFs were read via web fetch on 2026-11-18 and searched for adverse-event tables by individual trial. '
        'Saphnelo (anifrolumab): all AE tables pool studies 1013 (MUSE), 04 (TULIP-2) and 05 (TULIP-1). '
        'Benlysta (belimumab): the file found contained only the filing checklist.'),
   script='Manual review (no script)',
   sources='https://www.accessdata.fda.gov/drugsatfda_docs/nda/2021/761123Orig1s000MultidisciplineR.pdf ; https://www.accessdata.fda.gov/drugsatfda_docs/nda/2011/125370Orig1s000MedR.pdf',
   cols={'drug': C['drug'], 'application': ('FDA application number', 'BLA = Biologics License Application', 'FDA'), 'citation': C['citation'],
         'url': ('Link to the review PDF', 'URL', 'FDA Drugs@FDA'), 'locator': C['locator'], 'retrieved': C['retrieved'],
         'trial_specific': ('Does the review give AE counts per individual trial?', 'yes / no / unknown', 'Our reading of the review'),
         'note': ('What was found and how it is used', 'text', 'Our reading of the review')},
   caveats='Pooled counts cannot enter the trial-level prediction task; analysed descriptively only. Figures read through an automated PDF reader must be checked on the PDF page before citing.'),
 'build/pairs_all_sources.csv': dict(
   title='Trial-event pairs with risk differences, all sources (analysis dataset)',
   row='One trial x active arm x MedDRA term x seriousness category x source. Each active arm is paired with the placebo arm of the same trial.',
   how=(HOW_CT + ' ' + HOW_PUB + ' 01_build_pairs.py stacks the CT.gov tables, groups by trial / seriousness / term, pairs every active arm with placebo '
        'and computes rd = a/n1 - c/n0. Publication rows take the organ class of the matching CT.gov term.'),
   script='scripts/01_build_pairs.py',
   sources='data/registry_ctgov.csv; data/articles.csv',
   cols=pick(['source', 'nct_id', 'trial', 'drug', 'route', 'phase', 'fu', 'arm', 'dose', 'event_type', 'soc', 'term', 'a', 'n1', 'c', 'n0', 'rd', 'locator', 'retrieved', 'period', 'citation']),
   caveats=('period and citation are filled only for publication rows; locator/retrieved are blank for the 3 trials taken from the earlier snapshot. '
            'Counts are never given to the model - only drug, route, dose, event_type, soc, term, phase, fu, n1, n0.')),
 'build/ctgov_serious_counts.csv': dict(
   title='CT.gov serious-event counts per trial, term and arm',
   row='One trial x MedDRA term x arm, for terms in the CT.gov Serious adverse events table.',
   how=('Built by 01_build_pairs.py from the CT.gov data: serious-table rows summed per trial, term and arm. Used by 03_describe_misses.py to flag terms that also '
        'have serious events (publication "any AE" counts include them; the CT.gov non-serious table does not).'),
   script='scripts/01_build_pairs.py',
   sources='ClinicalTrials.gov API v2',
   cols={'nct_id': C['nct_id'], 'ae_term': C['ae_term'], 'arm': ('Arm (active or placebo)', 'CT.gov arm label', 'CT.gov'), 'ctgov_serious': C['ctgov_serious']},
   caveats='Includes placebo arms.'),
 'results/coverage_by_trial_source_method.csv': dict(
   title='Conformal coverage and interval width by test trial, source, model and method',
   row='One test trial x model x method x target source.',
   how=('For each trial with a publication (TULIP-1, TULIP-2, BLISS-76): hold it out; train on CT.gov records of the other 4 trials; build 90% intervals; '
        'check whether each interval contains the CT.gov RD and the publication RD for the pairs BOTH sources report (matched pairs). '
        'A: residuals from leave-one-trial-out models within the 4 training trials (CV+). B: as A, with separate margins for serious and non-serious events. '
        'C: margin from publication records of the other published trials (exploratory). D: train on 3 trials, calibrate on 1, rotated (one row per calibration trial). '
        'A Null model (predict RD = 0) is the baseline. Coverage CIs are exact (Clopper-Pearson).'),
   script='scripts/02_cross_source_conformal.py (alpha = 0.10; GradientBoostingRegressor n_estimators=300, max_depth=3, learning_rate=0.05, random_state=0)',
   sources='build/pairs_all_sources.csv',
   cols=pick(['test_trial', 'model', 'method', 'target_source', 'n_pairs', 'covered', 'coverage', 'ci_lo', 'ci_hi', 'width_pp']),
   caveats='TULIP-2 rows mix common and serious AEs (10 + 4 pairs); see coverage_by_event_category for the split. Small n -> wide CIs. Exploratory.'),
 'build/coverage_by_event_category.csv': dict(
   title='Coverage by event category (common vs serious AEs), GBM model, methods A-C',
   row='One test trial x method x event category x target source.',
   how='03_describe_misses.py regroups pair_level_predictions.csv by seriousness category and recomputes coverage, exact 95% CI and median width.',
   script='scripts/03_describe_misses.py',
   sources='build/pair_level_predictions.csv',
   cols=pick(['test_trial', 'method', 'event_category', 'target_source', 'covered', 'n_pairs', 'coverage', 'ci95', 'median_width_pp']),
   caveats='Serious-AE rows exist only for TULIP-2 (4 pairs). Method C has no publication serious-AE calibration records, so its serious-AE interval is unbounded (inf).'),
 'build/pair_level_predictions.csv': dict(
   title='Pair-level predictions and intervals for every matched pair (GBM model, methods A-C)',
   row='One matched trial-event pair (reported by both CT.gov and the publication) x conformal method: 52 pairs x 3 methods.',
   how=('Produced by 02_cross_source_conformal.py: CT.gov and publication records of the held-out trial are joined on term, arm and seriousness; '
        'the model prediction and interval half-width are attached; coverage is checked against each source.'),
   script='scripts/02_cross_source_conformal.py',
   sources='build/pairs_all_sources.csv',
   cols=pick(['source', 'nct_id', 'trial', 'drug', 'route', 'phase', 'fu', 'arm', 'dose', 'event_type', 'soc', 'term', 'a_ct', 'n1', 'c_ct', 'n0', 'rd_ct',
              'locator', 'retrieved', 'period', 'citation', 'rd_pub', 'a_pub', 'c_pub', 'n1_pub', 'n0_pub', 'method', 'pred', 'half_width', 'cov_ct', 'cov_pub']),
   caveats='"source" says ctgov because the row structure comes from the CT.gov record; publication values are in the *_pub columns. period/citation are empty here (CT.gov side).'),
 'results/source_differences_and_misses.csv': dict(
   title='Where CT.gov and the publication differ, and whether interval misses coincide with those differences',
   row='One matched trial-event pair (52 rows), using method A intervals.',
   how=('03_describe_misses.py takes the method A predictions, adds CT.gov serious counts for the same term, computes count and RD differences between sources, '
        'and assigns CANDIDATE explanations by fixed rules: identical counts; denominator (n differs); seriousness split (term also in the CT.gov serious table '
        'while the article counts any AE); follow-up window (article period differs from the CT.gov time frame). These are possible explanations, not verified causes.'),
   script='scripts/03_describe_misses.py',
   sources='build/pair_level_predictions.csv; build/ctgov_serious_counts.csv',
   cols={**pick(['trial', 'arm', 'term', 'event_type', 'a_ct', 'n1', 'c_ct', 'n0', 'a_pub', 'n1_pub', 'c_pub', 'n0_pub', 'rd_ct', 'rd_pub', 'pred', 'half_width', 'cov_ct', 'cov_pub']),
         'ser_a': ('CT.gov serious-table count for this term, active arm', 'count', 'ctgov_serious_counts'),
         'ser_c': ('CT.gov serious-table count for this term, placebo arm', 'count', 'ctgov_serious_counts'),
         'abs_rd_diff_pp': ('Absolute difference between CT.gov and publication RD', 'percentage points', '|rd_ct - rd_pub| x 100'),
         'discordant': ('Covered in one source but missed in the other', 'TRUE / FALSE', 'cov_ct != cov_pub'),
         'candidate_explanations': ('Rule-based candidate reasons for a count difference', 'text (rules in "How it was obtained")', '03 script rules'),
         'ctgov_window': ('CT.gov adverse-event time frame', 'text', 'CT.gov record'),
         'pub_window': ('Publication analysis period', 'text', 'Article methods / table')},
   caveats='All three trials differ in follow-up window at trial level, so that label is broad. TULIP-1 publication numbers and window are to be re-verified.'),
 'build/omissions_by_trial.csv': dict(
   title='Common-AE pairs reported by one source but not the other',
   row='One trial with a publication.',
   how='03_describe_misses.py compares the set of (term, arm) pairs in the CT.gov non-serious table with the set in the publication common-AE table.',
   script='scripts/03_describe_misses.py',
   sources='build/pairs_all_sources.csv',
   cols={'trial': C['trial'],
         'ctgov_common_pairs': ('Common-AE pairs in CT.gov (non-serious table)', 'count', 'CT.gov'),
         'pub_common_pairs': ('Common-AE pairs in the publication table', 'count', 'Publication'),
         'in_both': ('Pairs reported by both', 'count', 'set intersection'),
         'ctgov_only': ('Pairs in CT.gov but not in the publication', 'count', 'set difference'),
         'pub_only': ('Pairs in the publication but not in CT.gov', 'count', 'set difference'),
         'ctgov_only_terms': ('Terms in CT.gov only', 'list', 'set difference'),
         'pub_only_terms': ('Terms in publication only', 'list', 'set difference')},
   caveats=('TULIP-1 "ctgov_only" (136) mostly reflects our INCOMPLETE extraction (6 terms), not omissions by the article. '
            "TULIP-2 and BLISS-76 differences reflect the articles' reporting thresholds (>5% in drug arm; >=10% any group).")),
 'results/same_trial_cross_report_summary.csv': dict(
   title='MAIN RESULT - same trial, other report: coverage summary',
   row='One model x method x trial (plus "All trials"), pooled over 100 repeats of a 5-fold event-level split.',
   how=('05_same_trial_cross_report.py. Unit = event (trial, term, arm, seriousness); registry and article versions of an event share a fold. '
        'For each fold: test = k, calibration = k+1, training = the rest; training and calibration use ClinicalTrials.gov only. '
        'Coverage is measured (1) on all registry test events, (2) on the registry values of events the article reports, '
        '(3) on the article values of those events. (1)->(2) = effect of WHICH events the article reports; (2)->(3) = effect of the article\'s numbers.'),
   script='scripts/05_same_trial_cross_report.py 100 (alpha = 0.10; seeds 1000-1099)',
   sources='build/pairs_all_sources.csv',
   cols={'model': C['model'], 'method': ('Conformal margin', 'A. one margin for all events; B. Mondrian = separate margins for serious and non-serious events', '05 script'),
         'trial': ('Trial whose test events are summarised', 'trial name or All trials', '05 script'), 'repeats': ('Number of repeated 5-fold splits', 'count', '05 script'),
         'cov_all_registry': ('Coverage on all registry test events (1)', 'fraction; guarantee says about 0.90', 'pooled over folds and repeats'),
         'cov_paper_events_registry_values': ('Coverage on events the article reports, registry values (2)', 'fraction', 'pooled'),
         'cov_paper_events_paper_values': ('Coverage on the same events, article values (3)', 'fraction', 'pooled'),
         'cov_common_registry': ('As (2), common (non-serious) AEs only', 'fraction', 'pooled'), 'cov_common_paper': ('As (3), common (non-serious) AEs only', 'fraction', 'pooled'),
         'mean_width_all_pp': ('Mean full interval width, all test events', 'percentage points', 'pooled'),
         'mean_width_paper_events_pp': ('Mean full interval width, events the article reports', 'percentage points', 'pooled'),
         'test_events_per_repeat_all': ('Registry test events per repeat', 'count (each event tested once per repeat)', '05 script'),
         'test_events_per_repeat_matched': ('Events also reported by the article, per repeat', 'count', '05 script'),
         'selection_effect_pp': ('Coverage change from WHICH events the article reports: (2) - (1)', 'percentage points', 'calculated'),
         'value_effect_pp': ('Coverage change from the article\'s different numbers: (3) - (2)', 'percentage points', 'calculated')},
   caveats='3 trials and 52 matched events. TULIP-1 article rows await re-verification. Exploratory.'),
 'build/same_trial_fold_level.csv': dict(
   title='Same-trial test: counts for every repeat x fold (the numbers behind the summary)',
   row='One repeat x fold x model x method x trial.',
   how='Written by 05_same_trial_cross_report.py before pooling; summing the count columns over rows reproduces same_trial_cross_report_summary.',
   script='scripts/05_same_trial_cross_report.py', sources='build/pairs_all_sources.csv',
   cols={'rep': ('Repeat number', '0-99', 'seed = 1000 + rep'), 'fold': ('Test fold', '0-4', '05 script'), 'model': C['model'],
         'method': ('Conformal margin', 'A or B (see summary file)', '05 script'), 'trial': ('Trial', 'name or All trials', '05 script'),
         'n_all': ('Registry test events in this fold', 'count', '05 script'), 'cov_all_ct': ('...of which covered', 'count', '05 script'),
         'n_matched': ('Test events the article also reports', 'count', '05 script'), 'cov_matched_ct': ('...covered, registry values', 'count', '05 script'),
         'cov_matched_pub': ('...covered, article values', 'count', '05 script'), 'n_matched_common': ('Matched common (non-serious) events', 'count', '05 script'),
         'cov_matched_common_ct': ('...covered, registry values', 'count', '05 script'), 'cov_matched_common_pub': ('...covered, article values', 'count', '05 script'),
         'width_sum_all': ('Sum of full interval widths, all test events', 'proportion units', '05 script'), 'width_sum_matched': ('Sum of full widths, matched events', 'proportion units', '05 script')},
   caveats='Rows for trials without an article have n_matched = 0.'),
 'build/same_trial_pair_level.csv': dict(
   title='Same-trial test: every prediction for every matched event (GBM, method A)',
   row='One matched event x repeat (52 events x 100 repeats = 5,200 rows).',
   how='Written by 05_same_trial_cross_report.py: the out-of-fold prediction, the conformal half-width, and coverage against both reports.',
   script='scripts/05_same_trial_cross_report.py', sources='build/pairs_all_sources.csv',
   cols={'rep': ('Repeat number', '0-99', 'seed = 1000 + rep'), 'fold': ('Fold the event was tested in', '0-4', '05 script'), 'model': ('Row type', 'pairs', '05 script'),
         'method': ('Conformal margin', 'A. one margin', '05 script'), 'trial': C['trial'], 'term': C['term'], 'arm': C['arm'], 'event_type': C['event_type'],
         'rd_ct': C['rd_ct'], 'rd_pub': C['rd_pub'], 'pred': C['pred'], 'q': ('Conformal half-width', 'proportion', 'calibration quantile'),
         'cov_ct': C['cov_ct'], 'cov_pub': C['cov_pub']},
   caveats='Flips between cov_ct and cov_pub show where the article\'s numbers alone change the verdict (155 of 5,200).'),
 'build/selection_event_coverage.csv': dict(
   title='Selective-reporting test: out-of-fold coverage rate for every registry event',
   row='One registry event (trial x term x arm x seriousness); 1,352 rows.',
   how='06_selection_proof.py repeats the same-trial design 40 times (method A) and records, per event, the share of repeats in which its interval covered the registry value (and the article value, if reported).',
   script='scripts/06_selection_proof.py 40', sources='build/pairs_all_sources.csv',
   cols={**pick(['source', 'nct_id', 'trial', 'drug', 'route', 'phase', 'fu', 'arm', 'dose', 'event_type', 'soc', 'term', 'a', 'n1', 'c', 'n0', 'rd', 'rd_pub']),
         'reported': ('Does the article report this event?', 'TRUE / FALSE', 'matched on trial, term, arm, seriousness'),
         'freq': ('Event frequency: the higher of the two arms\' incidence', 'proportion', 'max(a/n1, c/n0), registry'),
         'fbin': ('Frequency band', '<2%, 2-5%, 5-10%, >=10%', 'from freq'),
         'cov_ct': ('Share of 40 repeats in which the interval covered the registry value', 'fraction', '06 script'),
         'cov_pub': ('Same, article value (reported events only)', 'fraction', '06 script')},
   caveats='Used for the randomization test; see results/selection_test_stats.json for p-values.'),
 'results/selection_coverage_by_frequency.csv': dict(
   title='Coverage by event-frequency band (Figure 1, panel A)',
   row='One frequency band.',
   how='06_selection_proof.py groups selection_event_coverage by frequency band.',
   script='scripts/06_selection_proof.py 40', sources='build/selection_event_coverage.csv',
   cols={'fbin': ('Frequency band', '<2%, 2-5%, 5-10%, >=10%', 'max arm incidence, registry'), 'n_all': ('Registry events in band', 'count', '06'),
         'cov_all': ('Mean coverage, all registry events', 'fraction', '06'), 'n_paper': ('Article-reported events in band', 'count', '06'),
         'cov_paper_registry': ('Mean coverage, reported events, registry values', 'fraction', '06'), 'cov_paper_paper': ('Same, article values', 'fraction', '06'),
         'n_unreported_ph3': ('Unreported events in phase 3 trials', 'count', '06'), 'cov_unreported_ph3': ('Mean coverage, those events', 'fraction', '06')},
   caveats='Bands with n_paper = 2 are too small to interpret.'),
}

F = Font(name='Arial', size=10)
FB = Font(name='Arial', size=10, bold=True)
FT = Font(name='Arial', size=13, bold=True)
HDR = PatternFill('solid', start_color='D9E1F2')
WR = Alignment(wrap_text=True, vertical='top')
thin = Border(bottom=Side(style='thin', color='999999'))

for rel, doc in DOCS.items():
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        print(f'skip {rel} (not built yet - run make all)'); continue
    df = doc['loader'](path) if 'loader' in doc else pd.read_csv(path)
    wb = Workbook()
    ab = wb.active
    ab.title = 'About'
    ab['A1'] = doc['title']
    ab['A1'].font = FT
    meta = [('File', rel + '   (this .xlsx is a documented copy; the analysis scripts read the original ' + os.path.basename(rel) + ')'),
            ('What one row is', doc['row']),
            ('Rows x columns', f'{len(df)} rows x {len(df.columns)} columns (sheet "Data")'),
            ('How it was obtained', doc['how']),
            ('Produced by', doc['script']),
            ('Sources', doc['sources']),
            ('Trials', TRIALS_TXT),
            ('Caveats', doc['caveats']),
            ('Documented', '2026-11-18; regenerate with scripts/04_make_documented_xlsx.py')]
    r = 3
    for k, v in meta:
        ab.cell(r, 1, k).font = FB
        ab.cell(r, 1).alignment = WR
        c = ab.cell(r, 2, v)
        c.font = F
        c.alignment = WR
        ab.row_dimensions[r].height = 14 * (len(str(v)) // 90 + 1)
        r += 1
    r += 1
    ab.cell(r, 1, 'Column dictionary (sheet "Data")').font = FT
    r += 1
    for j, h in enumerate(['Column', 'Meaning', 'Units / values', 'Where it comes from'], 1):
        c = ab.cell(r, j, h)
        c.font = FB
        c.fill = HDR
    r += 1
    for col in df.columns:
        m = doc['cols'].get(col, ('(undocumented)', '', ''))
        for j, v in enumerate([col, *m], 1):
            c = ab.cell(r, j, v)
            c.font = F
            c.alignment = WR
            c.border = thin
        ab.row_dimensions[r].height = 14 * max(len(m[0]) // 90 + 1, len(m[1]) // 50 + 1, len(m[2]) // 40 + 1)
        r += 1
    for col, w in zip('ABCD', [26, 95, 55, 42]):
        ab.column_dimensions[col].width = w

    ws = wb.create_sheet('Data')
    for j, col in enumerate(df.columns, 1):
        c = ws.cell(1, j, col)
        c.font = FB
        c.fill = HDR
        c.alignment = WR
        m = doc['cols'].get(col)
        if m:
            c.comment = Comment(f'{m[0]}. Units/values: {m[1]}. Source: {m[2]}', 'Claude', width=320, height=130)
        p90 = int(df[col].astype(str).str.len().quantile(.9)) if len(df) else 8
        ws.column_dimensions[get_column_letter(j)].width = min(45, max(10, len(col) + 2, p90 + 2))
    for i, row in enumerate(df.itertuples(index=False), 2):
        for j, v in enumerate(row, 1):
            if isinstance(v, (np.bool_, bool)):
                v = bool(v)
            elif isinstance(v, np.integer):
                v = int(v)
            elif isinstance(v, (float, np.floating)):
                v = float(v)
                if np.isnan(v):
                    v = None
                elif np.isinf(v):
                    v = 'inf'
            c = ws.cell(i, j, v)
            c.font = F
            col = df.columns[j - 1]
            if isinstance(v, float):
                if col in ('rd', 'rd_ct', 'rd_pub', 'pred', 'half_width'):
                    c.number_format = '0.0000'
                elif col in ('coverage', 'ci_lo', 'ci_hi'):
                    c.number_format = '0.0%'
                else:
                    c.number_format = '0.00'
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    out = os.path.splitext(path)[0] + '.xlsx'
    wb.save(out)
    und = [c for c in df.columns if c not in doc['cols']]
    print(f'{out}: {len(df)} rows, {len(df.columns)} cols, undocumented={und}')
