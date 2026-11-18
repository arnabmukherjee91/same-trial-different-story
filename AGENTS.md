# Rules for AI agents working in this repository

These rules apply to any AI agent that reads, extracts, analyses or edits here.
A person reviews every change before it is used in a result.

## Agents may do autonomously
- Pull public trial records through official APIs (ClinicalTrials.gov API v2) and save them in `data/registry_ctgov.csv`.
- Propose extractions from article and FDA tables, *with a locator* (table number or page) and the retrieval date.
- Run, rerun and extend the analysis scripts; regenerate figures and the documented Excel copies.
- Open issues that describe discrepancies, with evidence.

## Guardrails (must hold for every change)
1. **Identity check.** Before using any record, confirm that its NCT number matches the registry title, arms and doses. Labels are never trusted on their own.
2. **Checksums.** `data/registry_ctgov.csv` must match the live API: the same number of rows per trial and the same summed counts. Record both in the audit log.
3. **Provenance on every number.** Each extracted count carries its source, citation, table locator and retrieval date. Every row needs one.
4. **Not reported is not zero.** An event a source does not list is recorded as missing, never as 0.
5. **Cross-table consistency.** When one quantity appears in two places in a document, both values are recorded. If they disagree, the item is flagged for a person to check on the page. Neither value is picked silently.
6. **No circumvention.** Never bypass access controls, logins, bot checks or rate limits. A blocked source is logged and handed to a person.
7. **Trial-level splits.** A trial's registry, article and FDA records always stay in the same training, calibration or test group. Leakage across reports is a bug.
8. **Baselines are reported.** Every model result is shown next to the null model (RD = 0), including when the null model does as well.
9. **Reproducibility.** `make reproduce` must pass before a result is cited. Update `checksums/expected.md5` only together with a logged reason.
10. **No overclaiming.** Conformal coverage is reported with exact binomial intervals. Claims about guarantees under shift are not allowed.

## A person decides
Trial identity corrections, MedDRA mapping disputes, reconciliation between extractors, inclusion of new trials, and all interpretation and wording of claims.

## Logging
Each working session adds an entry to the audit log below: what was done, which guardrail fired, and what a person decided.

## Audit log

Each entry records what the AI agent did, which guardrail fired, and what the author decided.

### 2026-11-18 - session 1 (project start)

**Agent:** AI research agent. **Reviewer:** A. Mukherjee.

| # | Step | Guardrail | Event | Decision / status |
|---|---|---|---|---|
| 1 | Pulled ClinicalTrials.gov results for 5 trials (API v2) | Checksums against the live API | TULIP-1 160 terms / 1,092 summed counts; TULIP-2 60 / 425; BLISS-76 246 / 2,565; BLISS-52 165 / 1,972; NCT02962960 75 / 111. All matched | Snapshots accepted |
| 2 | Checked trial identities | NCT ↔ registry title and arms | An earlier internal dataset labelled NCT00410384 as "MEDI-4920" (it is **BLISS-76**, belimumab) and NCT02962960 as "TULIP-2" (it is a **36-patient phase 2 subcutaneous anifrolumab study**). TULIP-2 is NCT02446899 | Labels corrected in `data/registry_ctgov.csv`; counts unchanged |
| 3 | Searched the FDA Saphnelo review (BLA 761123) for per-trial AE tables | Study numbers ↔ arms; cross-table consistency | All AE tables pool MUSE, TULIP-1 and TULIP-2. "Study 04" = TULIP-2, "Study 05" = TULIP-1. The automated reading gave herpes zoster as 75/44 (Table 56) and as 28/6 (Table 63) for the same pooled population | FDA used descriptively only. **Resolved:** 28/6 is correct, confirmed in Tummala et al., *Lupus Sci Med* 2021 (PMC7893670), Table 2; 75/44 was the nasopharyngitis row |
| 4 | Benlysta FDA review (BLA 125370) | - | Medical review located (125370Orig1s000MedR.pdf): 212 pages of scanned images with no text layer, which is why automated reading saw only the checklist | **Open:** OCR, then extract per-trial tables |
| 5 | Extracted the TULIP-2 article (NEJM 2020, Table 3) and the BLISS-76 article (PMC5007058, Table 3) | Locator and date on every number; re-read against the page | 67 arm-level records | Accepted, single extractor |
| 6 | TULIP-1 article (ScienceDirect) | No circumvention | Bot check blocked access | Earlier extraction (6 terms) kept and flagged **re-verify**. **Open:** retrieve through the library |
| 7 | Ran the leave-one-trial-out and same-trial analyses | Trial- and event-level splits; null-model baseline | ML model about equal to the null model | Reported in the README |
| 8 | Reproducibility | Byte comparison | Outputs identical on Python 3.10 (Linux VM) and Python 3.13 (Linux container) | `checksums/expected.md5` created |
