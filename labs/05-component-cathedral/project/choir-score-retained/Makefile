.PHONY: all
LITAI_LANGUAGE_TOOL ?= python3
EXPORT_PATH ?= _build/choir-score.pyz
all:
	"$(LITAI_LANGUAGE_TOOL)" -m zipapp . -m 'main:run' -o "$(EXPORT_PATH)"
