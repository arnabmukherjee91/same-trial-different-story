PY ?= python3
SHELL := /bin/bash
.PHONY: reproduce all check excel verify-registry clean

## Fast path: build pairs, leave-one-trial-out test, miss analysis, then check outputs byte for byte
reproduce:
	cd scripts && $(PY) 01_build_pairs.py && $(PY) 02_cross_source_conformal.py && $(PY) 03_describe_misses.py
	$(MAKE) check FILES="build/pairs_all_sources.csv build/ctgov_serious_counts.csv build/pair_level_predictions.csv results/coverage_by_trial_source_method.csv results/source_differences_and_misses.csv"

## Everything: also the 100-repeat same-trial test, the 10,000-draw randomization test, and both figures
all: reproduce
	cd scripts && $(PY) 05_same_trial_cross_report.py 100 > ../build/same_trial_run_log.txt && $(PY) 06_selection_proof.py 40 && $(PY) 07_agentic_evidence_figure.py
	$(MAKE) check

## Compare outputs with checksums/expected.md5 (all files, or only FILES if given)
check:
	@if [ -z "$(FILES)" ]; then md5sum -c checksums/expected.md5; else grep -F -f <(printf '%s\n' $(FILES)) checksums/expected.md5 | md5sum -c -; fi

excel:
	cd scripts && $(PY) 04_make_documented_xlsx.py

verify-registry:
	cd scripts && $(PY) 00_verify_ctgov.py

clean:
	rm -rf build
