PYTHON  := .venv/bin/python3
MAIN    := main.py
ENC     ?= secrets.yml.enc
SRC     ?= secrets.yml
PORT    ?= 9371

.PHONY: install encrypt decrypt serve keychain-store help

## install: create venv and install dependencies
install: $(PYTHON)

## encrypt: encrypt SRC into ENC  (make encrypt SRC=secrets.yml ENC=secrets.yml.enc)
encrypt: $(PYTHON)
	$(PYTHON) $(MAIN) encrypt $(SRC) $(ENC)

## decrypt: decrypt ENC to stdout  (make decrypt ENC=secrets.yml.enc)
decrypt: $(PYTHON)
	$(PYTHON) $(MAIN) decrypt $(ENC)

## keychain-store: save password in Keychain with Touch ID protection (one-time setup)
keychain-store: $(PYTHON)
	$(PYTHON) $(MAIN) keychain-store

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
