function capture_gif_flow(in_mat, out_mat, method)
%CAPTURE_GIF_FLOW Native-fs reference FLOW (u/uu) for a weighted-LP GIF method.
%
%   The capture gate (capture_gif_weights) validated the weight and the AR solve;
%   this captures the END-TO-END flow -- inverse filter + de-emphasis -- that it
%   did not. Same pieces and the SAME inverse-filter path as capture_cp (lpcifilt
%   + de-emph), generalised to the method's weightsForLP weight, so the
%   lpcifilt-vs-v_lpcifilt question stays settled by cp's passing test.
%
%   The three continuous methods (ame/rgauss/agauss) read gci only; a gap-free goi
%   (pickGOIs) is passed solely to clear weightsForLP's any(goi-gci<=0) guard
%   (unused in those branches). v_lpccovar is the pinned AR oracle; weightsForLP
%   resolves to the authoritative Toolbox file. Reference paths via addpath.

L = load(in_mat);
sp = L.sp(:, 1); fs = double(L.fs);
gci = double(L.gci); goic = double(L.goic);
nsp = length(sp);

goi = pickGOIs(gci, goic);
par = projParam(method); wpar = par.wpar; wpar.fs = fs;
w = weightsForLP(gci, goi, nsp, wpar);

nar = ceil(fs / 1000);
wl = round(fs * par.fpar.wl); inc = round(fs * par.fpar.inc);
tstart = (nar + 1):inc:(nsp - wl - 1); tend = tstart + wl;

b = [1 -exp(-2 * pi * par.mpar.f_preemph / fs)];
a = sqrt(1 / sum(b .^ 2));
spp = filter(b, a, sp);

AR = zeros(numel(tstart), nar + 1); DC = zeros(numel(tstart), 1);
for f = 1:numel(tstart)
    [arf, ~, dcf] = v_lpccovar(spp, nar, [tstart(f) tend(f)], w(:));
    AR(f, :) = arf; DC(f) = dcf;
end
uu = lpcifilt(sp, AR, [tstart(:) tend(:)], DC, 0);
u = filter(a, b, uu);

save(out_mat, 'w', 'uu', 'u', 'tstart', '-v7');
fprintf('capture_gif_flow(%s): %d frames, %d samples\n', method, numel(tstart), nsp);
end
