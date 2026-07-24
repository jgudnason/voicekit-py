# Validation suite

Corpus-scale accuracy evaluation, separate from the unit tests in `tests/`
(see DESIGN.md §5). Not run in default CI: it needs external datasets and
is too slow for per-push checks. The ground-truth-construction and loader
code *is* unit-tested in CI on tiny synthetic inputs (`tests/validation/`);
only the corpus runs are excluded.

## Data location

External corpora are never committed. The OpenGlot root is resolved by strict
precedence — no default, no search, no fallback beyond this list:

1. `--openglot-root PATH`
2. else `$VOICEKIT_OPENGLOT_DIR`
3. else `$VOICEKIT_DATA_DIR/openglot`
4. else error, naming all three, exit nonzero.

The resolved root and *which rule resolved it* are recorded in every run's
`run_manifest`. The OpenGlot tree is expected as shipped:

```
<root>/
  RI/RepositoryI/Vowel_*/<VOWEL>_<mode>_<f0>Hz.wav   # R1: 336 files, 2 channels
  RII/RepositoryII_{male,female}/...                 # R2: 3 channels
```

`$VOICEKIT_DATA_DIR/openglot/` (the README's earlier expectation) still works
via rule 3; the tree shape itself is data, pinned by the manifest, not hardcoded.

## The manifest — the reproducibility pin

`validation/openglot/manifest_r1.tsv` is committed. It is generated **once** by
an explicit emission and thereafter only *verified*, never silently regenerated:

```
python -m validation.openglot.cli --emit-manifest --out validation/openglot/manifest_r1.tsv \
    --openglot-root /path/to/OpenGlot
```

Each row pins one file: relpath, whole-file sha256, flow-channel sha256, fs,
channels, samples, and the (vowel, mode, f0) parsed from the filename and
cross-checked against the file. The scored set comes from this manifest, so a
result's exact inputs are always reconstructible. R1 has 336 rows, 336 distinct
file hashes, and 56 distinct flow-channel hashes (the flow is bit-identical
across the 6 vowels; see REFERENCE_NOTES OG-GCI-D).

## Output

All generated output (metrics tables, plots, intermediate dumps, per-run
`run_manifest`) goes under `validation/results/`, which is gitignored in full.
Nothing under `results/` is ever committed.
