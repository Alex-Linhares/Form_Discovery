function fx_util(outfile)
% Fixture for src/formdiscovery/util.py and weights.py (item 07, L0-a): vec, inv_triu,
% inv_posdef, logdet, mylogdet, sumlogs, meanlogs, mysetdiff, subv2ind, trans2orig,
% matrixpartition, triplepartition, weightprior. Inputs are deterministic (seeded randn)
% and saved next to the outputs. Indices are saved 1-based, as Octave returns them.
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
addpath(fullfile(here, '..', 'matlab', 'formdiscovery1.0'));
randn('state', 7); rand('state', 7);
out = struct();

% --- vec -------------------------------------------------------------------------
out.vec_a = reshape(1:12, 3, 4) .^ 2;
out.vec_v = vec(out.vec_a);
out.vec_a3 = reshape(1:12, 2, 3, 2);
out.vec_v3 = vec(out.vec_a3);

% --- SPD matrices: inv_triu, inv_posdef, logdet, mylogdet ----------------------------
ns = [1 3 8 20];
spd = cell(1, numel(ns));
for k = 1:numel(ns)
  X = randn(ns(k), ns(k) + 2);
  spd{k} = X * X' + ns(k) * eye(ns(k));
end
% chol reads only the upper triangle: an SPD upper triangle over a garbage lower one
S = spd{2}; S(2, 1) = S(2, 1) + 5; S(3, 1) = -7;
spd{end + 1} = S;
% the kind of matrix mylogdet sees in graph_like_conn.m:90 (inv of a PD "-H")
spd{end + 1} = inv(spd{3});
out.spd = spd;
out.chol_U = cell(size(spd)); out.inv_triu = cell(size(spd));
out.inv_posdef = cell(size(spd));
out.logdet = zeros(1, numel(spd)); out.mylogdet = zeros(1, numel(spd));
for k = 1:numel(spd)
  U = chol(spd{k});
  out.chol_U{k} = U;
  out.inv_triu{k} = inv_triu(U);
  out.inv_posdef{k} = inv_posdef(spd{k});
  out.logdet(k) = logdet(spd{k});
  out.mylogdet(k) = mylogdet(spd{k});
end
% ill-conditioned but PD: logdet only
out.hilb = hilb(6);
out.hilb_logdet = logdet(out.hilb);
out.hilb_mylogdet = mylogdet(out.hilb);

% --- mylogdet fallback (chol fails -> log(det(A))) -----------------------------------
Q = orth(randn(3));
npd = {Q * diag([-1 2 3]) * Q', ...        % det < 0 -> complex
       Q * diag([-1 -2 3]) * Q', ...       % det > 0 -> real
       [1 1; 1 1], ...                      % singular PSD, det = 0 -> -Inf
       [2 3; 1 -4], ...                     % non-symmetric, det < 0
       -spd{2}};                            % negative definite, det < 0
out.npd = npd;
out.npd_logdet = cell(size(npd));
out.npd_isreal = zeros(1, numel(npd));
out.npd_logdet_err = zeros(1, numel(npd));
for k = 1:numel(npd)
  y = mylogdet(npd{k});
  out.npd_logdet{k} = y;
  out.npd_isreal(k) = isreal(y);
  try
    logdet(npd{k});
  catch
    out.npd_logdet_err(k) = 1;
  end
end

% --- sumlogs / meanlogs ----------------------------------------------------------------
lx = {[0 0 0], [-1 -2 -3]', [1000 1001 999.5], [-1e4 -1e4-1 -1e4-3], ...
      [-Inf 0 -2], [-Inf -Inf], 3.5, randn(1, 30) * 50, ...
      [-Inf 1 2; 3 -Inf 0; 0.5 0.5 -1; 2 2 2]};
out.logs_x = lx;
out.sumlogs = cell(size(lx)); out.meanlogs = cell(size(lx));
for k = 1:numel(lx)
  out.sumlogs{k} = sumlogs(lx{k});
  out.meanlogs{k} = meanlogs(lx{k});
end

% --- mysetdiff --------------------------------------------------------------------------
ma = {[5 1 3 3 9], [2 2 4], [], [4 1], [7 2 7 1], [3 1 2]};
mb = {[3 7 1], [], [1 2], [4 1 4], [7], [9 8]};
out.msd_a = ma; out.msd_b = mb; out.msd = cell(size(ma));
for k = 1:numel(ma)
  out.msd{k} = mysetdiff(ma{k}, mb{k});
end

% --- subv2ind ---------------------------------------------------------------------------
[a, b, c] = ndgrid(1:2, 1:2, 1:2);
siz = {[2 2 2], [3 4 2], 5, [4 3], [2 2], [4 3]', [3 4 2]};
subv = {[a(:) b(:) c(:)], [1 1 1; 3 4 2; 2 1 2; 3 2 1; 1 4 2], [1; 5; 3], ...
        [1 1; 4 3; 2 3; 3 1], [2 1; 1 2], [2 3; 4 1], zeros(0, 3)};
out.s2i_siz = siz; out.s2i_subv = subv; out.s2i = cell(size(siz));
for k = 1:numel(siz)
  out.s2i{k} = subv2ind(siz{k}, subv{k});
end
out.s2i_emptysiz = subv2ind([], [1 2 3]);

% --- trans2orig ---------------------------------------------------------------------------
out.t2o_P = [0.1 0.5 0.9; 0.25 0.75 1];
out.t2o_S = [2 4 10; 0.5 1 3];
[out.t2o_alpha, out.t2o_beta] = trans2orig(out.t2o_P, out.t2o_S);

% --- matrixpartition / triplepartition -----------------------------------------------------
J = reshape(1:81, 9, 9) + 0.5 * eye(9);
out.part_J = J;
mp_n = [4 9 0 1];
out.mp_n = mp_n; out.mp = cell(numel(mp_n), 4);
for k = 1:numel(mp_n)
  [A, B, C, D] = matrixpartition(J, mp_n(k));
  out.mp(k, :) = {A, B, C, D};
end
tp = [3 2; 5 0; 0 4; 4 5];
out.tp_n = tp; out.tp = cell(size(tp, 1), 5);
for k = 1:size(tp, 1)
  [A1, A2, B1, B2, D] = triplepartition(J, tp(k, 1), tp(k, 2));
  out.tp(k, :) = {A1, A2, B1, B2, D};
end

% --- weightprior -------------------------------------------------------------------------
wv = {[0.5 1 2 4], [0.1; 0.2; 3], 0.7, [], exp(randn(1, 25))};
wb = [0.4 1 5 0.4 0.4];
out.wp_w = wv; out.wp_beta = wb; out.wp = zeros(1, numel(wv));
for k = 1:numel(wv)
  out.wp(k) = weightprior(wv{k}, wb(k));
end

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
