function capture_vuv_features(wav_path, out_mat)
%CAPTURE_VUV_FEATURES Run the reference vuvMeasurements on one fixture, dump FM + T.
%
%   Black-box capture: reads the fixture wav, runs the reference
%   inriaGIF/vus/vuvMeasurements.m with the ratified VUV grid parameters
%   (wl=0.032 s, inc=0.01 s, nar=16), and saves the feature matrix FM =
%   [Nz Es C1 alp1 Ep] together with T -- the per-frame [start end] sample
%   window bounds vuvMeasurements actually used. Nothing here is computed on
%   the Python side; MATLAB is the oracle.
%
%   audioread scales 16-bit PCM by 1/32768, matching voicekit read_wav, so the
%   captured FM is computed on the same samples the Python parity test reads.
%
%   Reference paths (inriaGIF/vus for vuvMeasurements; VOICEBOX for lpccovar and
%   enframe) are supplied by the caller via addpath before -batch.

[sp, fs] = audioread(wav_path);
if size(sp, 2) > 1
    sp = sp(:, 1);
end

par.wl = 0.032;
par.inc = 0.01;
par.nar = 16;
par.fs = fs;

[FM, T] = vuvMeasurements(sp, par);

save(out_mat, 'FM', 'T', 'fs', '-v7');
fprintf('capture_vuv_features: %s -> %d frames\n', wav_path, size(FM, 1));
end
