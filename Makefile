.PHONY: run ingest rebuild test
run:
	python3 -m failure_mode.server
ingest:
	python3 -m failure_mode.ingest
rebuild:
	python3 -m failure_mode.ingest --cached
test:
	python3 -m unittest discover -s tests -v
