function capture_features(fixture_npz_dir, out_mat, name)
%CAPTURE_FEATURES Run the reference feature extraction on one fixture, save outputs.
%
%   Black-box capture of the reference feature-extraction pipeline's public
%   returns (and the derived flow u, per the reference single-file harness). No instrumentation: the
%   function is called directly and its outputs saved. Inputs (udash, gci, fs)
%   come from the committed YAGA golden fixture, read here from a small .mat the
%   Python driver writes.
%
%   The reference paths are supplied by the caller via addpath before -batch.

in = load(fullfile(fixture_npz_dir, [name '_in.mat']));   % udash, gci, fs
udash = in.udash(:);
gci = double(in.gci(:)');
fs = double(in.fs);

uu = udash;   % the IAIF flow derivative == the fixture's udash

% Derived glottal flow u: the feature-specific leaky integrator from testSingleFile.m
f_preemph = 10;
b = [1 -exp(-2 * pi * f_preemph / fs)];
a = sqrt(1 / sum(b .^ 2));
u = filter(a, b, uu);

[mfdr, cq, pa, naq, f0, h1h2, hrf, qoq, framek, vuv] = extractVoiceFeatures(u, uu, fs, gci);

F.u = u(:);
F.mfdr = mfdr(:); F.cq = cq(:); F.pa = pa(:); F.naq = naq(:); F.f0 = f0(:);
F.h1h2 = h1h2(:); F.hrf = hrf(:); F.qoq = qoq(:); F.framek = framek(:); F.vuv = vuv(:);
F.ncycles = numel(mfdr);
F.ngci = numel(gci);

save(out_mat, '-struct', 'F', '-v7');
fprintf('capture_features: %s -> %d cycles for %d gci\n', name, F.ncycles, F.ngci);
end
