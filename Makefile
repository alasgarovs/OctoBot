# OctoBot developer tasks. Run from the repository root.
VENV ?= .venv

# Update .ts files from the source code (drops obsolete strings).
update-translations:
	for lang in en az ru; do \
		$(VENV)/bin/pylupdate6 src/app.py src/pages.py src/workers.py src/widgets.py \
			--no-obsolete --ts src/translations/app_$$lang.ts; \
	done

# Compile .ts -> .qm. (en mirrors the source text; fill az/ru in the .ts files first.)
compile-translations:
	for lang in en az ru; do \
		$(VENV)/bin/pyside6-lrelease src/translations/app_$$lang.ts \
			-qm src/translations/app_$$lang.qm; \
	done

# Regenerate icons/favicon.ico from the in-app logo.
favicon:
	$(VENV)/bin/python tools/make_favicon.py

.PHONY: update-translations compile-translations favicon
