# YAGA golden-master fixtures

MATLAB reference captures for the step-5 (YAGA GCI/GOI) port. Each Python
stage implemented under `src/voicekit/yaga/` is checked against the
reference's actual output at the corresponding stage boundary — and, so a
bug in an early stage can't cascade and mask a later stage's test, each
stage's **input** is captured too, letting every Python stage be driven
with MATLAB's own upstream output rather than with our own.

The reference is the published GPL'd DYPSA detector
(`vsaTools/YAGA/dypsagoi.m`, jointly copyrighted Kounoudes / Gudnason /
Naylor / Brookes). Per the project's licensing stance (see `DESIGN.md`),
the Python code is a from-scratch reimplementation from the published
algorithm, **not** a port of that source; these captures only pin the
numerical target.

## Files

- `<fixture>.npz` — all stage-boundary arrays for one input (see dictionary
  below). Committed; consumed by `tests/test_yaga_*.py`.
- `wfilters_bior15.npz` — `Lo_D`, `Hi_D` exactly as MATLAB
  `wfilters('bior1.5','d')` returns them. The convention reference the
  Python coefficient test asserts against (up to a known
  normalization/sign/tap-order transform, not raw equality).
- `capture/` — the capture harness (not run in CI):
  - `make_inputs.py` — regenerates the committed `data/fixtures/*.wav`
    inputs deterministically.
  - `instrument.py` — injects `save`-hooks into the reference at named
    anchor lines. Reads the reference at runtime; no GPL source is vendored
    into this repo.
  - `capture_one.m` — runs the instrumented detector on one fixture.
  - `capture_golden.py` — orchestrates instrument → run → convert to `.npz`.

## Inputs

Three synthetic vowels (Rosenberg pulse train through a fixed all-pole
vocal tract), committed as 16-bit PCM under `data/fixtures/`. PCM makes the
committed bytes the single source of truth — MATLAB `audioread` and
voicekit `read_wav` both scale int16 by 2**15, so both sides of each
comparison read bit-identical floats.

The IAIF residual length (`nu`) drives the SWT pad/trim path, which pads to
a multiple of `2^nlev = 8`:

| fixture             | fs    | residual `nu` | `nu % 8` | padded `nU` | pad |
|---------------------|-------|---------------|----------|-------------|-----|
| `vowel_f0100_16k`   | 16000 | 9600          | 0        | 9600        | 0   |
| `vowel_glide_16k`   | 16000 | 8837          | 5        | 8840        | 3   |
| `vowel_f0120_8k`    | 8000  | 4801          | 1        | 4808        | 7   |

The first skips padding; the other two exercise the pad-and-trim path.

## Reproducing

Requires MATLAB (+ Wavelet and Signal Processing toolboxes) and local
checkouts of VOICEBOX and vsaTools. Paths come from environment variables —
never hardcoded in committed algorithm code:

- `VOICEKIT_MATLAB` — MATLAB executable (default: local R2024b app path).
- `VOICEKIT_VOICEBOX` — VOICEBOX directory (provides `lpcauto`, `lpcifilt`,
  `voicebox`/`v_voicebox` parameter store).
- `VOICEKIT_VSATOOLS` — vsaTools directory (provides `iaif`, `dypsagoi`).

```
python tests/golden/capture/make_inputs.py     # only to regenerate inputs
python tests/golden/capture/capture_golden.py   # regenerate the .npz captures
```

## `.npz` field dictionary

Shapes below are for `vowel_f0100_16k` (`nu = 9600`); `N = nu`,
`Ncand` = number of GCI candidates. Vectors are 1-D float64; scalars are
0-d. All from the canonical `opt=''` run unless prefixed `vus_`.

**SWT setup / convention**
- `nlev` (=3), `nu`, `nU` — decomposition levels, residual length, padded
  length. `nU = 2^nlev * ceil(nu / 2^nlev)`.
- `Lo_D`, `Hi_D` `(10,)` — bior1.5 decomposition filters (also in
  `wfilters_bior15.npz`).

**Stage boundaries** (input → output at each step)
- `udash` `(N,)` — IAIF glottal-flow derivative; the SWT input.
- `swa`, `swd` `(3, N)` — SWT approximation and detail rows, trimmed to `nu`.
- `mp` `(N,)` — multiscale product `prod(swd)`.
- `nmp`, `crnmp` `(N,)` — negative half-wave-rectified `mp`, and its cube
  root (the group-delay input, GCI branch).
- `gdwav_raw`, `sew_raw`, `zcr_cand_raw` — raw `xewgrdel` outputs: group
  delay, phase-slope cost, zero-crossing candidate samples.
- `toff` — group-delay alignment offset.
- `gdwav` `(N-toff,)` — aligned group-delay function.
- `pro_cand` — phase-slope-projection recovered candidate samples.
- `s_used` `(N,)`, `fnwav` `(N-45,)` — pre-emphasized speech and its
  Frobenius-norm energy function (`frobfun`).
- `aencost`, `cencost` `(Ncand,)` — anticausal / causal closed-phase energy
  costs.
- `dp_gcic` `(Ncand, 2)`, `dp_sew` `(Ncand,)` — candidate set (sample,
  unprojected-flag) and phase-slope cost handed to the DP.
- `gci_dp` — GCIs chosen by the DP, before peak-refinement.
- `gci`, `goi` — final GCIs and GOIs.
- `ret_goic` `(Ngoicand, 2)` — GOI candidate set returned by the detector.
- `input_s` `(N,)`, `input_fs` — the fixture samples and rate, as read.

**DP cost decomposition** (from the `opt='v'` run, which uniquely computes
it; its full-length signals are bit-identical to the default run and are
not duplicated)
- `vus_dp_Cfn` `(Ncand,)` — Frobenius energy cost per candidate (`fnrg`).
- `vus_dp_mycost` `(Ngci, 5)` — per-selected-GCI cost columns (see below).
- `vus_dp_gci_costed`, `vus_gci` — GCIs the cost matrix rows correspond to,
  and the voicing-filtered final GCIs (`opt='v'` drops unvoiced candidates,
  so `vus_gci` differs from `gci`).

### The five DP cost columns (piece 4 builds to these, not four)

DESIGN.md's roadmap names four DP costs; the reference DP actually weights
**five** per-candidate terms, which is what `vus_dp_mycost` captures (columns,
in order, read straight off the reference's cost assembly):

1. **waveform similarity** — normalized cross-correlation of the speech
   around candidate vs. previous GCI (negative = similar = good); mostly
   negative here.
2. **pitch deviation** — cost of the implied period deviating from the
   running estimate.
3. **projected-candidate** — `(1 - unprojected_flag)/2`: a flat penalty for
   candidates recovered by phase-slope projection rather than a real
   zero-crossing. In {0, 0.5}; all 0 on these clean synthetic vowels
   (no projected candidate was selected).
4. **Frobenius energy** — the `fnrg`/`frobfun` energy cost (= `vus_dp_Cfn`
   at the selected candidates).
5. **phase-slope deviation** — `Ch`, the phase-slope cost per candidate
   (from `sew`).

The roadmap's fourth item, **closed-phase (anticausal) energy**, is *not* one
of these five columns: it enters the DP as a separate fixed-cost term added
into the per-candidate base cost, and is captured independently as
`aencost`/`cencost`. So the full per-candidate DP cost is these five weighted
terms plus the closed-phase term. Piece 4 should reproduce all six pieces,
validating the five weighted terms against `vus_dp_mycost` (unweighted, as
captured — the reference divides each back out by its weight) and the
closed-phase term against `aencost`.
