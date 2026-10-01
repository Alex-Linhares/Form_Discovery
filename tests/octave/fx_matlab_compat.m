function fx_matlab_compat(outfile)
% Fixture for src/formdiscovery/matlab_compat.py: Octave's answers for the MATLAB
% built-ins the sources rely on (find, hist, unique, set ops, mysetdiff, chol, sparse,
% median, sort, max). Inputs are deterministic and saved next to the outputs. All
% indices are saved 1-based, as Octave returns them.
% Excluded on purpose (Octave != MATLAB, see KNOWN_ISSUES.md): hist values exactly on a
% bin edge (KI-13) and hist(x, n) with even n on constant x.
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
addpath(fullfile(here, '..', '..', 'matlab', 'formdiscovery1.0'));
out = struct();

% --- find (column-major) ---------------------------------------------------------
A = [0 2 0 1; 3 0 0 4; 0 5 6 0];
out.find_A = A;
out.find_k = find(A);
[i, j, v] = find(A);
out.find_i = i; out.find_j = j; out.find_v = v;
out.find_row = find([0 1 0 1 1]);

% --- hist(x, centres) ----------------------------------------------------------------
hx = {[1 2 2 3 3 3], [1 2 2 3 3 3], [0 1 4 9 -2 2.2], [2 5 5 9 2], [3 3 3], ...
      [1 2 5 7 7.5 3], [4 4 1], [1 1 1 1], [1 NaN 2 2]};
hc = {1:3, 1:5, [1 2 3], [2 5 9], 3, 3, 1, 1, 1:2};
out.hist_x = hx; out.hist_c = hc;
out.hist_n = cell(size(hx));
for k = 1:numel(hx)
  out.hist_n{k} = hist(hx{k}, hc{k});
end
% the real call sites: hist(z, 1:n) on a cluster vector and hist(z, unique(z))
z = [1 3 3 2 5 5 5 1];
out.hist_z = z;
out.hist_z_range = hist(z, 1:6);
out.hist_z_unique = hist(z, unique(z));

% --- unique ------------------------------------------------------------------------
u = [3 1 3 2 1 2 7];
out.unique_a = u;
[b, i, j] = unique(u, 'first'); out.unique_b = b; out.unique_i_first = i; out.unique_j = j;
[b, i, j] = unique(u, 'last');  out.unique_i_last = i;
R = [1 0 1; 0 1 1; 1 0 1; 0 0 0; 0 1 1; 1 1 0];
out.urows_A = R;
[b, i, j] = unique(R, 'rows', 'first'); out.urows_b = b; out.urows_i_first = i; out.urows_j = j;
[b, i, j] = unique(R, 'rows', 'last');  out.urows_i_last = i;
% the real call site: scaledata.m:51 on judges (inf = missing)
load(fullfile(here, '..', '..', 'data', 'judges.mat'));
datamask = ~isinf(double(data));
[b, i, j] = unique(datamask', 'rows');
out.judges_b = double(b); out.judges_j = j;

% --- sorted set operations -----------------------------------------------------------
sa = {[5 1 3 3 9], [2 2], [], [4 1], []};
sb = {[3 7 1], [], [1 2], [4 1 4], []};
out.set_a = sa; out.set_b = sb;
out.setdiff = cell(size(sa)); out.intersect = cell(size(sa)); out.union = cell(size(sa));
for k = 1:numel(sa)
  out.setdiff{k} = setdiff(sa{k}, sb{k});
  out.intersect{k} = intersect(sa{k}, sb{k});
  out.union{k} = union(sa{k}, sb{k});
end

% --- mysetdiff (order-preserving, keeps duplicates) ----------------------------------
ma = {[5 1 3 3 9 1], [2 2], [], [4 1], [7 6 5]};
mb = {[3 7], [], [1 2], [4 1 4], [9]};
out.mys_a = ma; out.mys_b = mb; out.mys = cell(size(ma));
for k = 1:numel(ma)
  out.mys{k} = mysetdiff(ma{k}, mb{k});
end

% --- chol (upper) ----------------------------------------------------------------
M = [4 2 0.4; 2 5 1; 0.4 1 3];
out.chol_A = M;
[U, p] = chol(M); out.chol_U = U; out.chol_p = p;
N = [2 1 0 0; 1 2 1 0; 0 1 -3 1; 0 0 1 2];     % fails at column 3
out.chol_B = N;
[U, p] = chol(N); out.chol_Ub = U; out.chol_pb = p;
L = [1 5; 0 1];                                % lower triangle ignored
out.chol_C = L;
[U, p] = chol(L); out.chol_Uc = U; out.chol_pc = p;

% --- sparse accumulation ---------------------------------------------------------
e = [3 1 3 4 1 3];
out.sp_e = e;
out.sp_counts = full(sparse(1, sort(e), 1));
out.sp_i = [1 2 1 3]; out.sp_j = [2 2 2 1]; out.sp_v = [0.5 1 2 -1];
out.sp_full = full(sparse(out.sp_i, out.sp_j, out.sp_v, 3, 4));

% --- median ----------------------------------------------------------------------
md = {[3 1 2], [4 1 3 2], [], [1 NaN 3], 7};
out.med_x = md; out.med = zeros(1, numel(md));
for k = 1:numel(md)
  out.med(k) = median(md{k});
end

% --- sort (stable, NaN placement) ------------------------------------------------
sx = {[2 NaN 1 2 3 1], [5 5 5], [0.3 -1 NaN NaN 0.3 2]};
out.sort_x = sx;
out.sort_asc = cell(size(sx)); out.sort_desc = cell(size(sx));
for k = 1:numel(sx)
  [s, out.sort_asc{k}] = sort(sx{k});
  [s, out.sort_desc{k}] = sort(sx{k}, 2, 'descend');
end

% --- max (first index, NaN skipped) ----------------------------------------------
mx = {[1 3 3 2], [NaN 2 2], [NaN NaN], [-Inf NaN -Inf], [-1 -Inf], 4};
out.max_x = mx; out.max_m = zeros(1, numel(mx)); out.max_i = zeros(1, numel(mx));
for k = 1:numel(mx)
  [out.max_m(k), out.max_i(k)] = max(mx{k});
end

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
