.PHONY: install test dq-check dq-check-dirty run skew-check

DQ_REFERENCE_DATETIME ?= 2026-09-13T12:00:00

install:
	pip install -r requirements-dev.txt

test:
	pytest

dq-check:
	python -m src.quality_gate --input data/input/sample_clean.csv \
		--reference-datetime $(DQ_REFERENCE_DATETIME)

dq-check-dirty:
	python -m src.quality_gate --input data/input/sample_dirty.csv \
		--reference-datetime $(DQ_REFERENCE_DATETIME) || \
		echo "Falha esperada: sample_dirty.csv não deve passar no Quality Gate."

run:
	python -m src.pipeline

skew-check:
	python -m src.ml_skew_check --train data/input/sample_clean.csv --serving data/input/sample_serving.csv
