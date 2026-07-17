# Working method — three questions to ask inline

These are not step-7 lore. They are three failure modes that recurred while
building the voicing detector, each caught (or, in the cases below, *not* caught
until it was expensive) enough times to be worth a standing rule. They govern
future work directly: step 8's weighted-LP GIF comparison will have parameters
that attract fits (rule 1); step 9's scorer and YIN work inherit rule 3 whole.

Every rule here is **cheap at the point of use and expensive at review**. Asking
"was this fixed before I saw the fixture?" while writing the line costs a
sentence; discovering at review that a default was fitted costs the retraction,
the re-derivation, and the trust in every number near it. That asymmetry is the
whole argument for asking them inline rather than catching them later — and for
writing them down where the next session reads them cold, not where they are
rediscovered.

The cases are kept attached on purpose. "Don't fit parameters" is forgettable;
"k=1 sat at 97% of the survival boundary" is not. None of the decisions cited is
re-opened here — every one is closed and correctly recorded in `REFERENCE_NOTES.md`.
These are the method's findings about *how it caught them*.

---

## 1. Was this parameter fixed before its fixture outcome was visible?

**A fit finds whatever freedom the structure leaves.** Closing one hiding place
does not close the game; the fit moves to the next free parameter.

*The case.* The `r1` threshold was deliberately split into two terms —
`threshold = rho_env + z(alpha)/sqrt(N)` — specifically so the fit could not
hide in `alpha` (an earlier attempt had `alpha` coming out numerically equal to
D3's measured aspiration colour: `z ~ 6.1`, `6.1/sqrt(512) = 0.270`, a
significance level wearing a colour margin's clothes). The decomposition worked
— and the fit moved to `k`, the construction parameter for `rho_env`. `k = 1`
was chosen at **97% of the survival boundary** (D3's breathy voice survives only
for `k < 1.032`), which is not a coincidence a reader should be asked to accept.
It was retracted, and `rho_env` became a **declared range** rather than a pinned
point (`docs/vuv_rho_env.md`).

*The rule.* Ask this **at the moment a parameter acquires a default**, not at
review — because at review you already believe the default, and the question
reads as rhetorical. If you cannot answer "yes, the rule that sets it was fixed
before its fixture outcome was visible," the default is suspect.

*The structural fix that ended it.* `rho_env` became a **required parameter with
no default**. A parameter with no default has nothing to fit: the caller
declares it, the fixtures check the declaration, and the circularity is gone by
construction rather than by vigilance. Prefer this fix where the parameter is
genuinely a deployment property the caller can supply.

---

## 2. Is this caution evidenced, or merely cited?

**A caution repeated is not a caution tested.** Citations accumulate the *feel*
of support without adding any; a claim passed hand to hand can be load-bearing
and false at the same time.

*The cases — two for two when finally probed.*
- "The reference's own decision stage applied `medfilt1` to smooth `C1` — it
  knew per-frame `C1` was noisy and smoothed." This was leaned on **repeatedly**
  as independent corroboration for VUV8's null derivation. It was **false**: the
  reference's only `medfilt1` is a median on the *label sequence*, the paper's
  3-level contour smoothing, and nothing in the reference smooths `C1` at all
  (VUV15). The corroboration never existed.
- VUV16: the ratified caution that the ~70 Hz sub-band check might false-positive
  on a low male voice, because 50/60 Hz hum sits near the bottom of modal
  phonation. Measured: an 85 Hz voice carries a sub-70 Hz energy fraction of
  0.0008 — a **125x margin** below the threshold. The feared overlap does not
  exist; the caution was more conservative than its evidence.
- VUV18: the D1 "mask exercise" was cited across five gates as proving the
  per-cycle mask's GCI→frame lookup. Reading it showed it never called
  `project()` — it built the mask from ground-truth region membership and
  asserted beyond the guard band W, exactly where `project()` and membership
  *agree*, so it could not fail for the reason it was cited. **A test can be a
  citation too**, and "the test covers X" is checkable by reading the test.

The first two changed no decision — the decisions rested on the arguments that
could carry them (the derivation is math; the check's confidence ordering had
independent grounds), not on the hollow corroborations. The third was a coverage
claim, not a decision, but the same shape: an assertion repeated until someone
read it. All three were caught by **reading the source / running the
measurement**, never by re-reasoning.

*The rule.* A caution the build is **about to lean on** gets probed against
source or measurement before it carries weight. Not every caution — one the
decision actually depends on. "The reference does X" is checkable in the
reference; "feature Y overlaps region Z" is measurable on a fixture. Do the
check before the weight goes on.

---

## 3. Are you reasoning from a summary when the distribution is in hand?

When the exact computation or the full distribution is available and cheap, a
first-order model or a summary statistic is **not a prediction — it is a guess
wearing a derivation's clothes**.

*The cases — three for three across step 7's predictions.*
- **Held.** H0's conditioning delta (−0.0017) transferred to D1's `voiced_steady`
  within **0.0001** — because it transferred a *measured analogue*, not a model.
- **Missed by sign.** `rho_env` caveat (a) predicted D2's and D3's conditioning
  deltas at −0.045; measured **+0.002 / +0.009** — wrong sign, on exactly the
  two regions with content. Cause: a first-order filter model ("attenuate the
  fundamental, unity elsewhere") stood in for the exact computation — `|H|^2`
  against each region's *own measured spectrum* — which was available and cheap
  and reproduced all four deltas to within **0.0005**. The standing finding: for
  a gently tilted filter the passband term is not a correction to the stopband
  term, it *dominates*, and only the exact computation shows it.
- **Missed.** D3 breathy's detection was predicted from the region **mean**
  (0.625): "voiced iff `rho_env < 0.537`." The per-frame span **[0.593, 0.661]**
  governed — so even at the range's floor the threshold cuts breathy's lower
  tail, and **no admissible `rho_env` detects breathy voice at HNR ~ 0
  completely** (VUV17). The mean hid the tail where the answer lived.

*The rule.* If the exact computation is available and cheap, run it; if the full
distribution is in hand, use it. A summary is a prediction only when the summary
is all you have.

*The connection, because it generalizes past prediction.* This is the **same
rule VUV5/VUV11 already impose on scoring** — never report an aggregate,
stratify — for the same reason: a mean hides the frames where discrimination
lives (D1's low-SNR tail, D2's fricative, breathy's lower tail). Prediction and
scoring are the same failure at two scales. **Step 9's scorer is where this bites
hardest**: a per-region mean is exactly the aggregate the ledger already forbids
it from reporting, and the pull toward computing one will be strong.

---

## The common mechanism (not a fourth rule)

All three were caught the same way: by **reading the source or taking the
measurement — never by re-reasoning from what was already believed**. This is
not a fourth question to ask; it is how the other three are *answered*. Each one,
when it fires, resolves to an external act — open the reference file, run the
exact filter, measure the region's distribution — because the failure in every
case was a belief that felt derived and wasn't. Reasoning harder about a wrong
premise produces a more confident wrong answer. The premise has to be checked
against something outside your own reasoning, and that is always cheaper inline
than at review.
