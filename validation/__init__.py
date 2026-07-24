"""Corpus-scale validation suite (see DESIGN.md section 5).

Importable so its ground-truth-construction code can be unit-tested in default
CI on tiny synthetic inputs, while the corpus runs themselves stay out of CI.
The scored corpora and all generated output are never committed.
"""
