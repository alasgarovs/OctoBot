# Update .ts files from source code
update-translations:
	for ts in src/translations/app_*.ts; do \
		pylupdate6 src/app.py --ts "$$ts"; \
	done

# Compile .ts → .qm
compile-translations:
	lrelease src/translations/*.ts

# Clean compiled .qm files
clean:
	rm -f src/translations/*.qm

# Convert .ui files to .py
convert:
	python ui_to_py.py