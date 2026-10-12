# Universal Koei Tecmo Save Editor v1.91

This reliability update applies the shared save-validation fix across the 75
registered scalar game/platform editors. Pending values are checked before they
reach a writer, unchanged opened values remain byte-exact no-ops, and every
edited copy is reopened to verify native integrity and confirm each requested
value was actually applied. Sixteen older direct backend APIs and the Nioh 3
adapter now reject malformed pending edits consistently. The contributor
template carries these checks into future scalar profiles. Save As also reopens
the actual destination file and verifies the saved bytes and requested values
before accepting the copy.

The library contains **76 game/platform profiles across 13 platforms**. The
source catalog records 30+ additional game/edition/platform research leads,
including some already covered by the broader 22-title format survey. No
unregistered profile was added without matching title/platform format,
integrity and writable-field evidence.

Download **UniversalKoeiTecmoSaveEditor-v1.91.exe** for the standalone Windows app,
or the **Windows ZIP** with the same executable and user documentation. No Python
installation is needed.

From source, install with `python -m pip install -e .` and run `python -m koei_editor`.
