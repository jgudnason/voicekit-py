function capture_wcovar(in_mat, out_mat)
%CAPTURE_WCOVAR Capture v_lpccovar weighted solve on the probe fixture.
%   Loads s, W, order, t from IN_MAT; runs the reference v_lpccovar with the
%   weight vector W (as the reference applies it) on both the plain 2-output
%   path and the 3-output dc_offset path; saves AR/energy/dc to OUT_MAT (-v7
%   so scipy.io.loadmat reads it). VOICEBOX path supplied by caller addpath.

d = load(in_mat);
s = d.s(:);
W = d.W(:);
order = d.order;
t = d.t;

% Plain weighted path (nargout=2 -> no dc offset in the LPC equations).
[ar_plain, e_plain] = v_lpccovar(s, order, t, W);

% dc_offset weighted path (nargout=3 -> DC term fitted jointly), the form
% weightedlpc.m actually calls: [ar,ee,dc]=lpccovar(sp,nar,T,w).
[ar_dc, e_dc, dc] = v_lpccovar(s, order, t, W);

out = struct();
out.ar_plain = ar_plain(:);
out.e_plain  = e_plain(:);
out.ar_dc    = ar_dc(:);
out.e_dc     = e_dc(:);
out.dc       = dc(:);
out.s        = s;
out.W        = W;
out.order    = order;
save(out_mat, '-struct', 'out', '-v7');
fprintf('capture_wcovar: wrote %s\n', out_mat);
end
