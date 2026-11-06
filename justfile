# Note: the venv interpreter is unusable for running
# the app itself (EPREFIX points into the venv, breaking portage),
# so `run` always uses the system interpreter.

# Run the TUI live (Gentoo system python only).
run *args:
    python3 -m carnage.main {{ args }}

# Test suite.
test *args:
    uv run pytest {{ args }}

# Regenerate man/carnage.1 from the markdown source.
man:
    lowdown -s -Tman -o man/carnage.1 docs/carnage.1.md
