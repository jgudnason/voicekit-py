# Instructions for Claude Code

This file is committed to the repo — it's project convention, not personal
configuration, and being upfront about it fits the project's disclosure
goals (see README "Development process"). The `.claude/` directory, by
contrast, is gitignored: it holds machine-specific permissions and local
paths that don't belong in a public repo.

## Committing

- Never commit without explicit, per-commit approval from the user. Do not
  treat approval of one commit as approval for a later one.
- When a commit is approved, author it under the user's own git identity
  only. Do **not** add a `Co-Authored-By: Claude` (or similar) trailer —
  this project is human-led and human-reviewed; commits should read as the
  user's own work.

## Provenance

- This project draws on a long line of prior MATLAB research code by the
  user. When referring to that history in docs, comments, or commit
  messages, do not name the user's informal, unpublished legacy project
  directories or their internal filenames — refer to them generically
  (e.g. "prior research code") instead. Publicly released prior work
  (the user's `vsaTools` repo, VOICEBOX, published papers) may be named
  and cited freely.

## Design principles

See [DESIGN.md](DESIGN.md) for the full rationale. In short:
- Domain algorithms (LPC, IAIF, the YAGA/DYPSA GCI-GOI detector, weighted-LP
  GIF methods, LF-model fitting, feature extraction) are implemented from
  first principles / from published algorithm descriptions — not ported
  from existing GPL'd code (notably Mike Brookes's VOICEBOX), even where
  VOICEBOX is used as a reference for what the algorithm should do. Credit
  VOICEBOX explicitly in module docstrings where it's the reference
  implementation being followed.
- Numerical primitives (FFT, linear algebra, standard filtering/resampling)
  via numpy/scipy are fine — the "first principles" rule applies to the
  voice-science algorithms, not the numerical substrate.
- No global mutable configuration. Every algorithm takes an explicit,
  typed config object.
- `tests/` (fast, fixture-based, CI-gated) is kept separate from
  `validation/` (corpus-scale accuracy runs against external datasets;
  slow, not part of default CI, output never committed).
