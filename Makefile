PYTHON  := .venv/bin/python3
MAIN    := main.py
ENC     ?= secrets.yml.enc
SRC     ?= secrets.yml
PORT    ?= 9371

.PHONY: install encrypt decrypt edit serve help

## install: create venv and install dependencies
install: $(PYTHON)

## encrypt: encrypt SRC into ENC  (make encrypt SRC=secrets.yml ENC=secrets.yml.enc)
encrypt: $(PYTHON)
	$(PYTHON) $(MAIN) encrypt $(SRC) $(ENC)

## decrypt: decrypt ENC to stdout  (make decrypt ENC=secrets.yml.enc)
decrypt: $(PYTHON)
	$(PYTHON) $(MAIN) decrypt $(ENC)

## edit: open ENC in $$EDITOR and re-encrypt on save  (make edit ENC=secrets.yml.enc)
edit: $(PYTHON)
	$(PYTHON) $(MAIN) edit $(ENC)

## serve: start local HTTP API  (make serve ENC=secrets.yml.enc PORT=9371)
serve: $(PYTHON)
	$(PYTHON) $(MAIN) serve $(ENC) $(PORT)

## help: show usage
help: $(PYTHON)
	@$(PYTHON) $(MAIN)

# Auto-create venv when requirements.txt changes
$(PYTHON): requirements.txt
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt
