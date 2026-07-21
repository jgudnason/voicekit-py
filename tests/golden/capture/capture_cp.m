function capture_cp(in_mat, out_mat)
%CAPTURE_CP Native-fs closed-phase reference capture for one fixture (GIF7).
%
%   Drives the reference closed-phase method at the fixture's native fs (no
%   20 kHz resample): reconstruct the GOIs, build the cp 0/1 weight, solve a
%   per-frame DC-offset covariance model, inverse-filter and de-emphasise --
%   the same pieces the reference weighted-LP driver composes, called directly.
%
%   Two faithful departures from the reference driver, both required to run it
%   at all and neither changing the method:
%     - the weight is passed to the covariance solver as a COLUMN. The reference
%       weighting constructor returns a 1xN row and the driver passes it through
%       to the solver, which errors on a column signal (a latent orientation bug
%       in the driver, fs-independent). w(:) is the intended usage.
%     - the per-frame solve is called frame-by-frame (the driver's batched
%       frame-matrix call hits the same row/column error); the model is identical.
%
%   Reference paths supplied by the caller via addpath before -batch.

L = load(in_mat);
sp = L.sp(:, 1); fs = double(L.fs);
gci = double(L.gci); goic = double(L.goic);

goi = pickGOIs(gci, goic);
par = projParam('cp'); wpar = par.wpar; wpar.fs = fs;
nsp = length(sp);
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

save(out_mat, 'w', 'goi', 'AR', 'DC', 'uu', 'u', 'tstart', '-v7');
fprintf('capture_cp: %d frames, %d samples\n', numel(tstart), nsp);
end
