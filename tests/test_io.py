"""Tests for wav I/O and resampling."""

from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from voicekit import Signal
from voicekit.io import read_wav, resample, write_wav


def sine(freq: float, fs: int, duration: float = 0.1, amp: float = 0.5) -> Signal:
    t = np.arange(int(duration * fs)) / fs
    return Signal(samples=amp * np.sin(2 * np.pi * freq * t), fs=fs)


def dominant_frequency(sig: Signal) -> float:
    spectrum = np.abs(np.fft.rfft(sig.samples))
    return float(np.argmax(spectrum) * sig.fs / sig.n_samples)


class TestWav:
    def test_roundtrip(self, tmp_path: Path) -> None:
        sig = sine(440, 8000)
        write_wav(sig, tmp_path / "a.wav")
        back = read_wav(tmp_path / "a.wav")
        assert back.fs == sig.fs
        assert back.source == str(tmp_path / "a.wav")
        # 16-bit quantization limits the achievable accuracy
        np.testing.assert_allclose(back.samples, sig.samples, atol=1 / 32767)

    @pytest.mark.parametrize(
        ("dtype", "scale"),
        [(np.int16, 2**15), (np.int32, 2**31)],
    )
    def test_reads_integer_pcm_scaled(self, tmp_path: Path, dtype: type, scale: int) -> None:
        pcm = np.array([0, scale // 2, -scale], dtype=dtype)
        wavfile.write(tmp_path / "pcm.wav", 8000, pcm)
        sig = read_wav(tmp_path / "pcm.wav")
        np.testing.assert_allclose(sig.samples, [0.0, 0.5, -1.0], atol=1e-9)

    def test_reads_uint8_pcm_scaled(self, tmp_path: Path) -> None:
        pcm = np.array([128, 192, 0], dtype=np.uint8)
        wavfile.write(tmp_path / "u8.wav", 8000, pcm)
        sig = read_wav(tmp_path / "u8.wav")
        np.testing.assert_allclose(sig.samples, [0.0, 0.5, -1.0], atol=1e-9)

    def test_reads_float_wav_unscaled(self, tmp_path: Path) -> None:
        data = np.array([0.0, 0.25, -0.75], dtype=np.float32)
        wavfile.write(tmp_path / "f32.wav", 8000, data)
        sig = read_wav(tmp_path / "f32.wav")
        np.testing.assert_allclose(sig.samples, data, atol=1e-7)

    def test_rejects_stereo_file_without_channel(self, tmp_path: Path) -> None:
        wavfile.write(tmp_path / "st.wav", 8000, np.zeros((100, 2), dtype=np.int16))
        with pytest.raises(ValueError, match="no default channel"):
            read_wav(tmp_path / "st.wav")

    def test_selects_channel_of_multichannel_file(self, tmp_path: Path) -> None:
        # Three distinct constant channels, as OpenGlot R2 ships
        # (pressure / glottal flow / glottal area): reading the wrong one is the
        # silent-wrong-answer this parameter exists to prevent.
        pcm = np.zeros((100, 3), dtype=np.int16)
        pcm[:, 0] = 2**14  # 0.5
        pcm[:, 1] = -(2**15)  # -1.0
        pcm[:, 2] = 2**13  # 0.25
        wavfile.write(tmp_path / "r2.wav", 44100, pcm)
        for ch, expected in ((0, 0.5), (1, -1.0), (2, 0.25)):
            sig = read_wav(tmp_path / "r2.wav", channel=ch)
            assert sig.fs == 44100
            np.testing.assert_allclose(sig.samples, np.full(100, expected), atol=1e-9)

    def test_channel_is_recorded_in_source(self, tmp_path: Path) -> None:
        wavfile.write(tmp_path / "st.wav", 8000, np.zeros((100, 2), dtype=np.int16))
        sig = read_wav(tmp_path / "st.wav", channel=1)
        assert sig.source == f"{tmp_path / 'st.wav'}#ch1"

    def test_rejects_out_of_range_channel(self, tmp_path: Path) -> None:
        wavfile.write(tmp_path / "st.wav", 8000, np.zeros((100, 2), dtype=np.int16))
        with pytest.raises(ValueError, match=r"channel must be in \[0, 1\]"):
            read_wav(tmp_path / "st.wav", channel=2)

    def test_mono_accepts_channel_zero_only(self, tmp_path: Path) -> None:
        wavfile.write(tmp_path / "m.wav", 8000, np.zeros(100, dtype=np.int16))
        assert read_wav(tmp_path / "m.wav", channel=0).n_samples == 100
        with pytest.raises(ValueError, match="is mono"):
            read_wav(tmp_path / "m.wav", channel=1)

    def test_write_rejects_out_of_range(self, tmp_path: Path) -> None:
        sig = Signal(samples=np.array([0.0, 1.5]), fs=8000)
        with pytest.raises(ValueError, match="rescale"):
            write_wav(sig, tmp_path / "loud.wav")


class TestResample:
    def test_upsample_preserves_frequency_and_duration(self) -> None:
        sig = sine(440, 8000, duration=0.5)
        up = resample(sig, 20000)
        assert up.fs == 20000
        assert up.n_samples == 10000
        assert dominant_frequency(up) == pytest.approx(440, abs=3)

    def test_downsample_preserves_frequency(self) -> None:
        sig = sine(440, 20000, duration=0.5)
        down = resample(sig, 8000)
        assert down.fs == 8000
        assert dominant_frequency(down) == pytest.approx(440, abs=3)

    def test_identity_when_fs_unchanged(self) -> None:
        sig = sine(440, 8000)
        assert resample(sig, 8000) is sig

    def test_rejects_bad_target(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            resample(sine(440, 8000), -1)
