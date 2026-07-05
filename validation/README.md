# Validation suite

Corpus-scale accuracy evaluation, separate from the unit tests in `tests/`
(see DESIGN.md §5). Not run in default CI: it needs external datasets and
is too slow for per-push checks.

## Data location

External corpora are never committed. Point the suite at your local data
via the `VOICEKIT_DATA_DIR` environment variable. Expected layout:

```
$VOICEKIT_DATA_DIR/
  openglot/    # OpenGlot synthetic vowels (known LF-model ground truth)
  aplawd/      # APLAWD corpus (laryngograph-referenced real speech)
```

## Output

All generated output (metrics tables, plots, intermediate dumps) goes
under `validation/results/`, which is gitignored in full. Nothing under
`results/` is ever committed.
