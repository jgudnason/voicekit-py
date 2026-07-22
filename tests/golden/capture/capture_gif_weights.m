function capture_gif_weights(in_mat, out_mat)
%CAPTURE_GIF_WEIGHTS Native-fs reference weight + per-frame AR for the three
%   continuous-weight GIF methods (AME, rgauss, agauss), for one fixture (GIF7).
%
%   The GIF1 convention seam is exercised LIVE for the first time here: unlike
%   cp's 0/1 mask (W^2==W, GIF1 a no-op), these weights are continuous, so W and
%   W^2 give different AR. This captures the reference side of that two-sided
%   check: the reference weight vector W (from the authoritative weighting
%   constructor) and the reference AR from the v_-prefixed covariance oracle,
%   per analysis frame, for each method.
%
%   Drives the SAME pieces the reference weighted-LP driver composes, called
%   directly at native fs (no 20 kHz resample): weightsForLP -> v_lpccovar. The
%   solve is the dc-offset 3-output form the driver actually calls
%   ([ar,ee,dc]=lpccovar(...)). v_lpccovar (NOT the unprefixed lpccovar alias,
%   which differs) is the pinned oracle; weightsForLP resolves to the authoritative
%   -0.5-present Toolbox file (the live driver's symbol), not weightsForLP_old.
%
%   The three methods read gci only; a valid gap-free goi (pickGOIs) is passed
%   solely to satisfy weightsForLP's any(goi-gci<=0) guard (unused in these
%   branches). Reference paths supplied by the caller via addpath before -batch.

L = load(in_mat);
sp = L.sp(:, 1); fs = double(L.fs);
gci = double(L.gci); goic = double(L.goic);
nsp = length(sp);

% Gap-free goi only to clear the guard (methods below never read it).
goi = pickGOIs(gci, goic);

% Pre-emphasis, exactly as the reference weighted-LP solve wrapper: estimate the
% AR on the pre-emphasised signal, power preserved. Captured so the Python side
% solves on IDENTICAL samples (isolating the QR solve, not preemph reproduction).
mpar_f_preemph = 5;   % Hz, projParam mpar.f_preemph
b = [1 -exp(-2 * pi * mpar_f_preemph / fs)];
a = sqrt(1 / sum(b .^ 2));
spp = filter(b, a, sp);

nar = ceil(fs / 1000);
wl = round(fs * 32e-3); inc = round(fs * 16e-3);   % projParam fpar.wl / .inc
tstart = (nar + 1):inc:(nsp - wl - 1); tend = tstart + wl;
nfr = numel(tstart);

methods = {'ame', 'rgauss', 'agauss'};
out = struct();
out.spp = spp(:);
out.tstart = tstart(:);
out.tend = tend(:);
out.nar = nar; out.wl = wl; out.nsp = nsp; out.fs = fs;

for mi = 1:numel(methods)
    m = methods{mi};
    par = projParam(m); wpar = par.wpar; wpar.fs = fs;
    W = weightsForLP(gci, goi, nsp, wpar);
    W = W(:);
    AR = zeros(nfr, nar + 1);
    for f = 1:nfr
        [arf, ~, ~] = v_lpccovar(spp, nar, [tstart(f) tend(f)], W);
        AR(f, :) = arf(:).';
    end
    out.(['w_' m]) = W;
    out.(['ar_' m]) = AR;
end

save(out_mat, '-struct', 'out', '-v7');
fprintf('capture_gif_weights: %d frames, %d samples, methods {ame,rgauss,agauss}\n', nfr, nsp);
end
