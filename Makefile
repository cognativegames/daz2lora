.PHONY: help setup test lint typecheck run build installer clean \
        setup-ssh setup-pc test-pc build-pc installer-pc

APP_NAME   := daz2lora
VENV       := .venv
PYTHON     := python3
SRC_DIR    := src
TEST_DIR   := tests

# ─── Load .env if present (gitignored, keeps PC host/user/dir local) ──────────
ifneq (,$(wildcard .env))
include .env
export
endif

PC_HOST    ?= MSI
PC_IP      ?= 192.168.1.7
PC_USER    ?= user
PC_DIR     ?= C:\Users\$(PC_USER)\Desktop\$(APP_NAME)

# Resolve PC: try hostname first, fall back to IP
PC_TARGET  := $(shell ping -c1 -W1 $(PC_HOST) >/dev/null 2>&1 && echo $(PC_HOST) || echo $(PC_IP))

RSYNC_OPTS := -avz --delete --exclude .venv --exclude __pycache__ --exclude .pytest_cache --exclude .env

# ═══ Mac-local (no PC needed) ═════════════════════════════════════════════════

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: $(VENV)/bin/pip  ## Create venv & install dev deps (Mac, for lint/typecheck/test)
	$(VENV)/bin/pip install -e ".[dev]"
	@echo "✓ Setup done. 118 unit tests run locally."

$(VENV)/bin/pip:
	$(PYTHON) -m venv $(VENV)

test: $(VENV)/bin/pip  ## Run 118 unit tests locally (no DAZ/kohya needed)
	$(VENV)/bin/python -m pytest $(TEST_DIR) -v --tb=short

test-coverage: $(VENV)/bin/pip  ## Unit tests with coverage
	$(VENV)/bin/python -m pytest $(TEST_DIR) -v --tb=short --cov=$(SRC_DIR) --cov-report=term-missing

lint: $(VENV)/bin/pip  ## ruff (Mac, fast)
	$(VENV)/bin/ruff check $(SRC_DIR) $(TEST_DIR)

typecheck: $(VENV)/bin/pip  ## mypy (Mac, fast)
	$(VENV)/bin/python -m mypy $(SRC_DIR)

run: $(VENV)/bin/pip  ## Launch app (Mac, screens 1-5 work, render/train will fail gracefully)
	$(VENV)/bin/python -m $(APP_NAME).main

clean:  ## Remove build artifacts
	rm -rf dist build *.spec __pycache__
	rm -rf $(SRC_DIR)/*.egg-info
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@echo "✓ Cleaned"

# ═══ Dev: edit on Mac → test/run on PC ════════════════════════════════════════

setup-ssh:  ## [one-time] Install SSH key on PC (password prompt)
	@echo "Checking SSH key..."
	@if [ ! -f ~/.ssh/id_ed25519.pub ]; then \
		echo "Generating SSH key..."; \
		ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519; \
	fi
	ssh-copy-id $(PC_USER)@$(PC_TARGET)
	@echo "✓ SSH key installed. All subsequent make commands are passwordless."

setup-pc:  ## [one-time] Install deps on PC
	ssh $(PC_USER)@$(PC_TARGET) "cd $(PC_DIR) && python -m venv .venv && .venv\Scripts\pip install -e ."

test-pc:  ## Rsync code to PC, run all tests, see results
	rsync $(RSYNC_OPTS) ./ $(PC_USER)@$(PC_TARGET):"$(PC_DIR)/"
	ssh $(PC_USER)@$(PC_TARGET) "cd $(PC_DIR) && .venv\Scripts\python -m pytest tests -v --tb=short"

run-pc:  ## Rsync code to PC, launch the app (full pipeline)
	rsync $(RSYNC_OPTS) ./ $(PC_USER)@$(PC_TARGET):"$(PC_DIR)/"
	ssh $(PC_USER)@$(PC_TARGET) "cd $(PC_DIR) && start .venv\Scripts\python -m $(APP_NAME).main"
	@echo "✓ App launched on PC. Check the Windows desktop."

build-pc:  ## Build daz2lora.exe on PC, pull it back to dist/
	rsync $(RSYNC_OPTS) ./ $(PC_USER)@$(PC_TARGET):"$(PC_DIR)/"
	ssh $(PC_USER)@$(PC_TARGET) \
		"cd $(PC_DIR) && .venv\Scripts\pip install pyinstaller && .venv\Scripts\pyinstaller --noconfirm --name $(APP_NAME) --windowed --add-data src/$(APP_NAME)/daz_scripts;$(APP_NAME)/daz_scripts --paths src --distpath dist --workpath build src/$(APP_NAME)/main.py"
	rsync -avz $(PC_USER)@$(PC_TARGET):"$(PC_DIR)/dist/" ./dist/
ifeq ($(OS),Windows_NT)
	@echo "✓ dist/$(APP_NAME)/$(APP_NAME).exe"
else
	@echo "✓ dist/$(APP_NAME)/$(APP_NAME).exe  (copy to Windows to run)"
endif

installer-pc:  ## Build daz2lora_setup.exe on PC (requires Inno Setup), pull back
	rsync $(RSYNC_OPTS) ./ $(PC_USER)@$(PC_TARGET):"$(PC_DIR)/"
	ssh $(PC_USER)@$(PC_TARGET) \
		"cd $(PC_DIR) && \"$(PROGRAMFILES)\\Inno Setup 6\\ISCC.exe\" scripts\\installer.iss"
	rsync -avz $(PC_USER)@$(PC_TARGET):"$(PC_DIR)/dist/daz2lora_setup.exe" ./dist/
	@echo "✓ dist/daz2lora_setup.exe"

pull:  ## Pull latest builds from PC
	rsync -avz $(PC_USER)@$(PC_TARGET):"$(PC_DIR)/dist/" ./dist/
	@echo "✓ Build files pulled to dist/"

# ─── Default ──────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help
