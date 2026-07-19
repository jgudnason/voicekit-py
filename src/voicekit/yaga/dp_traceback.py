"""DP traceback and peak-refinement -- the two post-DP stages of YAGA.

`traceback` reads the forward-pass trellis (`f_c`/`f_f`) back into the chosen
GCI sequence. `refine_gcis` then snaps each chosen GCI to a nearby peak of the
cube-root multiscale product. Both consume already-validated upstream tables /
arrays; neither feeds back into the DP.

The traceback reproduces a self-flagged reference bug (see REFERENCE_NOTES
entry 3): it starts from the *penultimate* candidate rather than the best
end-of-spurt node. That behaviour is quarantined behind
``force_penultimate`` -- a bug-compatibility switch, not a tuning knob.

References:
    P. A. Naylor, A. Kounoudes, J. Gudnason & M. Brookes (2007), DYPSA, IEEE
    TASLP 15(1), 34-43.

    Reference implementation: the traceback of ``dpgci`` and the peak-refinement
    (using VOICEBOX ``v_findpeaks``) of the reference GCI/GOI detector. Reimplemented from the
    algorithm description, not ported.
"""

import numpy as np
import numpy.typing as npt

from voicekit.yaga.dp_forward import DpConfig, DpForwardResult, append_boundary_states


def traceback(
    result: DpForwardResult,
    positions: npt.NDArray[np.int64] | npt.NDArray[np.float64],
    fs: float,
    config: DpConfig | None = None,
    force_penultimate: bool = True,
) -> npt.NDArray[np.int64]:
    """Reconstruct the chosen GCI sequence from the forward-pass trellis.

    ``positions`` are the assembled candidate positions in the same frame the
    forward pass used (1-based, as its window extraction requires); the returned
    GCIs are in that frame. ``force_penultimate`` selects the start node:

    * ``True`` (default) reproduces reference entry-3's **bug** for golden-master
      parity -- it forces the penultimate candidate (``i = rix(1) - dy_nbest``).
      The default is True only because the port's contract is to match the
      reference; this is bug-compatibility, not a preference.
    * ``False`` is the known-**correct** behaviour the reference's own comment
      specifies (``i = f_fb(Ncand+1)``, the best end-of-spurt node), pending
      validation-phase accuracy confirmation.
    """
    cfg = config if config is not None else DpConfig()
    nbest = cfg.nbest
    ncand = np.asarray(positions).shape[0]
    qrmax = int(np.floor(fs / cfg.fxmin))
    g_n = append_boundary_states(positions, qrmax)  # 1-based candidate positions
    f_c = result.f_c
    f_f = result.f_f + 1  # 1-based node backpointers (result stores 0-based)

    if force_penultimate:
        # Bug-compatible start node: penultimate candidate. See REFERENCE_NOTES
        # entry 3. `i` is a 1-based node index throughout the traceback.
        i = nbest * ncand + 1 - nbest
        if f_c[i - nbest + 1 - 1] < f_c[i - 1]:  # talkspurt-start check
            i = i - nbest + 1
    else:
        # Known-correct form: best end-of-spurt node f_fb(Ncand+1).
        i = int(result.f_fb[ncand]) + 1

    path = []
    while i > 1:
        candidate = 1 + (i - 1) // nbest  # 1-based candidate for this node
        path.append(g_n[candidate - 1])
        i = int(f_f[i - 1])
    return np.array(path[::-1], dtype=np.int64)


def _find_peaks(y: npt.NDArray[np.float64], min_sep: int) -> npt.NDArray[np.int64]:
    """Local maxima of ``y`` (plateau centred), lower of any pair within ``min_sep`` removed.

    Reimplements the behaviour of VOICEBOX ``v_findpeaks(y, '', min_sep)``: strict
    interior peaks with plateaus resolved to their (floored) centre, then the
    lower of any pair of peaks closer than ``min_sep`` samples eliminated (on a
    tie, the second). Returns 0-based indices. (scipy's peak finder does not
    match these plateau/elimination semantics, hence the reimplementation.)
    """
    y = np.asarray(y, dtype=np.float64)
    n = y.shape[0]
    if n < 3:
        return np.array([], dtype=np.int64)
    dy = np.diff(y)

    peaks = []
    i = 1
    while i < n - 1:
        if dy[i - 1] > 0:  # rose into sample i
            j = i
            while j < n - 1 and dy[j] == 0:  # traverse a plateau
                j += 1
            if j < n - 1 and dy[j] < 0:  # ... that then falls -> peak on [i, j]
                peaks.append((i + j) // 2)  # floored plateau centre
            i = j + 1
        else:
            i += 1
    k = np.array(peaks, dtype=np.int64)
    if k.size == 0 or min_sep <= 0:
        return k

    # Eliminate the lower of any pair closer than min_sep, iterating until none
    # remain (mirrors v_findpeaks' while-loop; ties drop the later peak).
    heights = list(y[k])
    ks = list(k)
    close = [idx for idx in range(len(ks) - 1) if ks[idx + 1] - ks[idx] <= min_sep]
    while close:
        drop = {idx + 1 if heights[idx] >= heights[idx + 1] else idx for idx in close}
        for idx in sorted(drop, reverse=True):
            del ks[idx]
            del heights[idx]
        close = [idx for idx in range(len(ks) - 1) if ks[idx + 1] - ks[idx] <= min_sep]
    return np.array(ks, dtype=np.int64)


def refine_gcis(
    gci: npt.NDArray[np.int64],
    crnmp: npt.NDArray[np.float64],
    tol: int = 10,
    min_sep: int = 50,
) -> npt.NDArray[np.int64]:
    """Snap DP-chosen GCIs to nearby peaks of ``-crnmp``; keep unmatched ones.

    Peaks of ``-crnmp`` (the strongest closures) are found; each GCI within
    ``tol`` samples of a peak is replaced by that peak, and GCIs matching no peak
    are kept as-is. ``gci`` is 1-based (as the traceback returns); ``crnmp`` is a
    0-based array, so peak indices are shifted to the 1-based frame. Returns
    sorted 1-based positions.
    """
    gci = np.asarray(gci, dtype=np.int64)
    peaks = _find_peaks(-np.asarray(crnmp, dtype=np.float64), min_sep) + 1  # 0-based -> 1-based

    within = np.abs(peaks[:, None] - gci[None, :]) < tol
    peak_idx, gci_idx = np.nonzero(within)
    unmatched = np.setdiff1d(np.arange(gci.size), gci_idx)
    return np.sort(np.concatenate([peaks[peak_idx], gci[unmatched]]))
