"""Iterative Adaptive Inverse Filtering (IAIF).

Estimates the glottal flow (and its derivative) from a speech signal by
iteratively modeling and removing the vocal tract and glottal source
spectral contributions with LPC.

References:
    P. Alku (1992), "Glottal wave analysis with Pitch Synchronous
    Iterative Adaptive Inverse Filtering", Speech Communication 11(2-3),
    109-118.

    P. Alku, H. Tiitinen, R. Naatanen (1999), "A method for generating
    natural-sounding speech stimuli for cognitive brain research",
    Clinical Neurophysiology 110(8), 1329-1333.

    Reference implementation: M. R. P. Thomas's MATLAB ``iaif.m`` (2009),
    which follows Alku (1999) and uses VOICEBOX ``lpcauto``/``lpcifilt``.
    Structure and defaults here mirror that implementation, including its
    reading of "integrator" as a slightly leaky integrator.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import scipy.signal

from voicekit.lpc.frames import inverse_filter_frames, lpc_auto_frames
from voicekit.signal import Signal


@dataclass(frozen=True)
class IaifConfig:
    """Parameters for `iaif`.

    The three LPC orders (the reference's letters ``p``, ``g``, ``r`` -- first
    vocal-tract, glottal-source, second vocal-tract) are **required**: there is no
    single fs-independent correct order, so a default would silently mismatch the
    caller's rate. For reference, ``iaif.m``'s function-signature arg-defaults are
    10/4/10, but the only in-project caller (``dypsagoi`` via `YagaConfig`) fixes
    **20/4/20 at every rate**, and Alku/Mark's presets (``iaif.m`` note 6) are
    8/2/8 at 8 kHz and 20/4/20 at 20 kHz. Pick per your rate and cite the source.
    """

    vt_order1: int  # p: first vocal tract LPC order
    glottal_order: int  # g: glottal source LPC order
    vt_order2: int  # r: second vocal tract LPC order
    highpass: bool = True  # remove low-frequency drift before analysis
    hpf_cutoff: float = 60.0  # Hz, per Alku (1999)
    hpf_taps: int = 1025  # linear-phase FIR length (order 1024)
    lpc_dur: float = 0.032  # s, analysis window, per Alku (1992)
    lpc_step: float = 0.016  # s, 50% overlap
    leak: float = 0.95  # leaky-integrator pole radius

    def __post_init__(self) -> None:
        if min(self.vt_order1, self.glottal_order, self.vt_order2) < 1:
            raise ValueError("LPC orders must be >= 1")
        if not 0 < self.leak < 1:
            raise ValueError(f"Leak must be in (0, 1), got {self.leak}")
        if self.hpf_taps % 2 == 0:
            raise ValueError("hpf_taps must be odd (linear-phase highpass FIR)")


@dataclass(frozen=True)
class IaifResult:
    """Output of `iaif`, all arrays aligned with the input signal."""

    glottal_flow_derivative: npt.NDArray[np.float64]
    glottal_flow: npt.NDArray[np.float64]
    vocal_tract: npt.NDArray[np.float64]  # final VT model, one row per frame
    frame_starts: npt.NDArray[np.int64]


def _leaky_integrate(x: npt.NDArray[np.float64], leak: float) -> npt.NDArray[np.float64]:
    return np.asarray(scipy.signal.lfilter([1.0], [1.0, -leak], x))


def iaif(signal: Signal, config: IaifConfig) -> IaifResult:
    """Estimate glottal flow and its derivative by IAIF.

    The twelve steps of Alku (1999): highpass; order-1 LPC and inverse
    filter (gross glottal tilt); first vocal tract LPC and inverse filter;
    integrate; glottal source LPC and inverse filter; integrate; second
    vocal tract LPC; final inverse filter gives the flow derivative, and
    one more integration the flow. Every inverse filter is applied to the
    highpassed input signal, not to the previous stage's output.

    ``config`` is required: the LPC orders are rate-dependent (see `IaifConfig`),
    so there is no safe default to fall back on.
    """
    cfg = config
    fs = signal.fs
    x = signal.samples

    frame_len = int(np.floor(cfg.lpc_dur * fs))
    hop = int(np.floor(cfg.lpc_step * fs))
    min_len = max(cfg.vt_order1, cfg.glottal_order, cfg.vt_order2) + 1
    if signal.n_samples < min_len:
        raise ValueError(f"Signal of {signal.n_samples} samples is too short for IAIF")

    # 1. Highpass to remove drift below the lowest plausible F0
    if cfg.highpass:
        b = scipy.signal.firwin(cfg.hpf_taps, cfg.hpf_cutoff, fs=fs, pass_zero=False)
        delay = (cfg.hpf_taps - 1) // 2
        spf = np.asarray(scipy.signal.lfilter(b, [1.0], x))
        spf = np.concatenate([spf[delay:], np.zeros(delay)])
    else:
        spf = x

    # 2-3. Order-1 LPC models the combined glottal tilt; remove it
    hg1, starts = lpc_auto_frames(spf, 1, frame_len, hop)
    s1 = inverse_filter_frames(spf, hg1, starts)

    # 4-5. First vocal tract estimate; remove from the highpassed input
    hvt1, starts = lpc_auto_frames(s1, cfg.vt_order1, frame_len, hop)
    s2 = inverse_filter_frames(spf, hvt1, starts)

    # 6. Integrate to a first glottal flow estimate
    s2i = _leaky_integrate(s2, cfg.leak)

    # 7-8. Model the glottal contribution; remove it from the input
    hg2, starts = lpc_auto_frames(s2i, cfg.glottal_order, frame_len, hop)
    s3 = inverse_filter_frames(spf, hg2, starts)

    # 9. Integrate (Alku 1999; not present in Alku 1992)
    s3i = _leaky_integrate(s3, cfg.leak)

    # 10-11. Final vocal tract model; inverse filter -> flow derivative
    hvt2, starts = lpc_auto_frames(s3i, cfg.vt_order2, frame_len, hop)
    udash = inverse_filter_frames(spf, hvt2, starts)

    # 12. Integrate -> glottal flow
    u = _leaky_integrate(udash, cfg.leak)

    return IaifResult(
        glottal_flow_derivative=udash,
        glottal_flow=u,
        vocal_tract=hvt2,
        frame_starts=starts,
    )
