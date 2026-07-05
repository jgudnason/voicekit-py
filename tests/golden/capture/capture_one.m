function capture_one(fixture_wav, out_mat, opt, override_residual_mat)
%CAPTURE_ONE Run the instrumented DYPSA reference on one fixture, dump GOLD.
%
%   capture_one(FIXTURE_WAV, OUT_MAT, OPT) reads FIXTURE_WAV, runs the
%   instrumented dypsagoi (which must shadow the reference on the path) with
%   option OPT ('' for the canonical run, 'v' to populate the DP per-candidate
%   cost decomposition), and saves the accumulated GOLD struct plus the
%   detector's returned outputs to OUT_MAT (-v7 so scipy.io.loadmat reads it).
%
%   capture_one(..., OVERRIDE_RESIDUAL_MAT) additionally loads a clean residual
%   from that .mat (variable ``udash``) and, via the global VK_OVERRIDE_UDASH
%   the instrumented copy checks, substitutes it for the internal IAIF estimate.
%   This drives the SWT and later stages with a clean input where the reference
%   IAIF is unusable (e.g. its NaN-prone 8 kHz residual). Pass '' to disable.
%
%   Paths to the reference toolboxes are supplied by the caller via addpath
%   before -batch invokes this function.

global GOLD VK_OVERRIDE_UDASH;
GOLD = struct();
VK_OVERRIDE_UDASH = [];
if nargin >= 4 && ~isempty(override_residual_mat)
    ov = load(override_residual_mat);
    VK_OVERRIDE_UDASH = ov.udash(:);
end

[s, fs] = audioread(fixture_wav);

if isempty(opt)
    [gci, goi, gcic, goic, gdwav, udash, crnmp] = dypsagoi(s, fs);
else
    [gci, goi, gcic, goic, gdwav, udash, crnmp] = dypsagoi(s, fs, opt);
end

% Detector return values (kept alongside the injected intermediates).
GOLD.ret_gci = gci(:);
GOLD.ret_goi = goi(:);
GOLD.ret_gcic = gcic;
GOLD.ret_goic = goic;
GOLD.ret_gdwav = gdwav(:);
GOLD.ret_udash = udash(:);
GOLD.ret_crnmp = crnmp(:);
GOLD.input_s = s(:);
GOLD.input_fs = fs;
GOLD.opt = opt;

save(out_mat, '-struct', 'GOLD', '-v7');
fprintf('capture_one: wrote %s (opt=''%s'')\n', out_mat, opt);
end
