function fx_l0b(outfile)
% Fixture for item 08 (L0-b): stirling2, hessiangrad, dijkstra, get_edgemap,
% find_descendants, expand_graph, makehyps, bbloglike, bblikesumhyps, dirmultloglike.
% Inputs are deterministic (seeded rand/randn, the demo data sets and the committed
% baseline graphs) and saved next to the outputs. Indices are saved 1-based.
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
addpath(fullfile(root, 'matlab', 'formdiscovery1.0'));
randn('state', 8); rand('state', 8);
out = struct();

% --- stirling2 -------------------------------------------------------------------
out.s2_nm = [40 40; 1 1; 1 5; 5 1; 8 8; 3 6; 12 12; 33 33; 0 3; 3 0];
out.s2 = cell(1, rows(out.s2_nm));
for k = 1:rows(out.s2_nm)
  out.s2{k} = stirling2(out.s2_nm(k, 1), out.s2_nm(k, 2));
end

% --- hessiangrad ---------------------------------------------------------------------
M = randn(4); out.hg_A = M + M'; out.hg_b = randn(4, 1);
out.hg_X = {randn(4, 1), zeros(4, 1), [0.5; -1; 2; 0.1]};
out.hg_e = [1e-5 1e-3 1e-5];
out.hg_shape = {[4 1], [1 4], [4 1]};
out.hg_H = cell(1, 3);
for k = 1:3
  out.hg_H{k} = hessiangrad('l0b_hessfun', out.hg_X{k}, out.hg_e(k), out.hg_A, out.hg_b, ...
                            out.hg_shape{k});
end
% length(dY) rows: a matrix-shaped gradient makes hessiangrad fail
try
  hessiangrad('l0b_hessfun', out.hg_X{1}, 1e-5, out.hg_A, out.hg_b, [2 2]);
  out.hg_matrix_err = 0;
catch
  out.hg_matrix_err = 1;
end

% --- adjacency matrices: demo data sets and baseline graphs ---------------------------
dnames = {'demo_chain_feat', 'demo_ring_feat', 'demo_tree_feat', 'demo_ring_rel_bin', ...
          'demo_order_rel_freq', 'demo_hierarchy_rel_bin'};
adjs = {}; adjnames = {};
for k = 1:numel(dnames)
  d = load(fullfile(root, 'data', [dnames{k} '.mat']));
  adjs{end + 1} = double(d.adj); adjnames{end + 1} = [dnames{k} '.adj'];
  if isfield(d, 'W')
    adjs{end + 1} = double(d.W); adjnames{end + 1} = [dnames{k} '.W'];
  end
  if isfield(d.graph, 'adjcluster')
    adjs{end + 1} = double(d.graph.adjcluster); adjnames{end + 1} = [dnames{k} '.adjcluster'];
  end
end
% final graphs of the Octave baseline (tests/fixtures/baseline): directed cluster graphs,
% their symmetric versions and weights (what swapobjclust/collapsedims pass to dijkstra)
graphs = {}; gnames = {};
for kind = {'feat', 'rel'}
  r = load(fullfile(root, 'tests', 'fixtures', 'baseline', kind{1}, 'resultsdemo.mat'));
  for i = 1:numel(r.structure)
    g = r.structure{i};
    if isstruct(g) && isfield(g, 'adjcluster')
      graphs{end + 1} = g; gnames{end + 1} = sprintf('%s%d.%s', kind{1}, i, g.type);
    end
  end
end
for k = 1:numel(graphs)
  g = graphs{k};
  adjs{end + 1} = double(g.adjcluster); adjnames{end + 1} = [gnames{k} '.adjcluster'];
  adjs{end + 1} = double(g.adjclustersym); adjnames{end + 1} = [gnames{k} '.adjclustersym'];
  if isfield(g, 'Wclustersym')
    adjs{end + 1} = double(g.Wclustersym); adjnames{end + 1} = [gnames{k} '.Wclustersym'];
  end
end
% constructed cases: upper/lower triangular with negative lengths (acyclic branch),
% NaN = zero-length arc, disconnected, random weighted digraph, 1x1
U = triu(randn(6), 1) .* (rand(6) > 0.3);
R = rand(9) .* (rand(9) > 0.6); R(1:10:end) = 0; R(2, 5) = NaN; R(7, 3) = NaN;
adjs = [adjs, {U, U', R, [0 1 0 0; 1 0 0 0; 0 0 0 2; 0 0 3 0], 0, [0 NaN; 1 0]}];
adjnames = [adjnames, {'triu_neg', 'tril_neg', 'rand_nan', 'disconnected', 'single', 'nan2'}];
out.adjs = adjs; out.adjnames = adjnames;

% --- dijkstra (all pairs) and get_edgemap on every matrix ------------------------------
out.dijk = cell(size(adjs)); out.emap = cell(size(adjs)); out.emapsym = cell(size(adjs));
for k = 1:numel(adjs)
  A = adjs{k};
  if ~any(any(tril(A) ~= 0)) || ~any(any(triu(A) ~= 0)) || ~any(any(A < 0))
    out.dijk{k} = dijkstra(A);
  else
    out.dijk{k} = [];
  end
  out.emap{k} = get_edgemap(A);
  out.emapsym{k} = get_edgemap(A, 'sym', 1);
end
% dijkstra with s/t subsets (length(t) < n stops early) on a few matrices
out.dst_k = cellfun(@(nm) find(strcmp(adjnames, nm)), ...
                    {'demo_chain_feat.adj', 'demo_tree_feat.W', 'rand_nan', 'triu_neg', 'tril_neg'});
out.dst_s = {[2 5], 14:-3:1, [9 1 4], 3, [6 1]};
out.dst_t = {[1 12 3], [], 2, [], [2 6]};
out.dst = cell(1, numel(out.dst_k));
for k = 1:numel(out.dst_k)
  out.dst{k} = dijkstra(adjs{out.dst_k(k)}, out.dst_s{k}, out.dst_t{k});
end
% error branches: non-square, negative on a cyclic graph, s and t out of range
errs = {{ones(2, 3)}, {[0 -1; 1 0]}, {R, 10}, {R, 1, 0}};
out.dijk_err = zeros(1, numel(errs));
for k = 1:numel(errs)
  try
    dijkstra(errs{k}{:});
  catch
    out.dijk_err(k) = 1;
  end
end

% --- find_descendants --------------------------------------------------------------
fd = {[0 1 1; 0 0 0; 0 0 0], ...                            % item 03b repro
      [0 1 1 0 0; 0 0 0 1 1; 0 0 0 0 0; 0 0 0 0 0; 0 0 0 0 0], ...  % 5-node tree
      [0 1 1 0; 0 0 0 1; 0 0 0 1; 0 0 0 0], ...              % DAG with a shared child
      [0 0 0; 1 0 0; 1 1 0], ...                             % edges pointing to lower ids
      zeros(4)};                                             % all leaves
fdnames = {'repro', 'tree5', 'diamond', 'lowerdag', 'empty4'};
for k = 1:numel(graphs)
  g = graphs{k};
  if any(strcmp(g.type, {'tree', 'hierarchy', 'order', 'domtree', 'dirhierarchy', ...
                         'dirhierarchynoself', 'undirhierarchy', 'undirhierarchynoself', ...
                         'ordernoself', 'dirchain', 'dirchainnoself', 'undirchain', ...
                         'undirchainnoself'}))
    for c = 1:numel(g.components)
      fd{end + 1} = double(g.components{c}.adj);
      fdnames{end + 1} = sprintf('%s.comp%d', gnames{k}, c);
    end
    A = double(g.adjcluster); A(1:rows(A) + 1:end) = 0;   % drop self links
    fd{end + 1} = A; fdnames{end + 1} = [gnames{k} '.adjcluster'];
  end
end
% big random DAG (upper triangular, so acyclic)
fd{end + 1} = triu(rand(25) > 0.8, 1); fdnames{end + 1} = 'randdag25';
out.fd_adj = fd; out.fd_names = fdnames;
out.fd = cell(size(fd)); out.fd_len = zeros(size(fd));
for k = 1:numel(fd)
  d = find_descendants(fd{k});
  out.fd_len(k) = numel(d);
  for i = numel(d) + 1:rows(fd{k})
    d{i} = [];                           % unassigned trailing cells (none expected)
  end
  out.fd{k} = d;
end

% --- expand_graph --------------------------------------------------------------------
out.eg_adj = {0, [0 1; 1 0], [0 1 1; 0 0 0; 0 0 0], zeros(3)};
out.eg_zs = {{1:5}, {[1 3], [2 4 5]}, {[], [2 1], [3]}, {[4 2], [], [1 3]}};
out.eg_new = cell(1, 4); out.eg_objcount = zeros(1, 4);
for k = 1:4
  [out.eg_new{k}, out.eg_objcount(k)] = expand_graph(out.eg_adj{k}, out.eg_zs{k}, 'x');
end

% --- makehyps (the grids of graph_like_rel.m) -----------------------------------------
out.mh_props = {(1:5) / 5 - 1 / 10, 0.5, [0.1 0.9]};
out.mh_sums = {2 .^ (1:5), 2 .^ (-3:2), [3 7 11]};
out.mh_alphas = cell(1, 3); out.mh_betas = cell(1, 3);
for k = 1:3
  [out.mh_alphas{k}, out.mh_betas{k}] = makehyps(out.mh_props{k}, out.mh_sums{k});
end

% --- bbloglike ---------------------------------------------------------------------
[al, be] = makehyps((1:5) / 5 - 1 / 10, 2 .^ (1:5));
ns = floor(rand(7, 1) * 20); ys = floor(rand(7, 1) .* (ns + 1)); ns(3) = 0; ys(3) = 0;
out.bb_alpha = repmat(al', 7, 1); out.bb_beta = repmat(be', 7, 1);
out.bb_ns = repmat(ns, 1, 25); out.bb_ys = repmat(ys, 1, 25);
out.bb_mat = bbloglike(out.bb_alpha, out.bb_beta, out.bb_ns, out.bb_ys);   % 1 x 25
out.bb_col = bbloglike(al, be, 10 * ones(25, 1), 3 * ones(25, 1));          % scalar
out.bb_row = bbloglike(al', be', 10 * ones(1, 25), 3 * ones(1, 25));        % 1 x 25, no sum

% --- bblikesumhyps -------------------------------------------------------------------
[aln, ben] = makehyps(0.5, 2 .^ (-3:2));
out.bs_ys = {ys, ys, [0; 0], zeros(0, 1), [5; 0; 2], [100; 3; 0]};
out.bs_ns = {ns, ns, [0; 0], zeros(0, 1), [5; 0; 9], [200; 50; 40]};
out.bs_hyp = [1 2 1 1 2 1];
hyps = {{al, be}, {aln, ben}};
out.bs = zeros(1, numel(out.bs_ys));
for k = 1:numel(out.bs_ys)
  h = hyps{out.bs_hyp(k)};
  out.bs(k) = bblikesumhyps(out.bs_ys{k}, out.bs_ns{k}, h{1}, h{2});
end
out.bs_al = al; out.bs_be = be; out.bs_aln = aln; out.bs_ben = ben;

% --- dirmultloglike -----------------------------------------------------------------
A = rand(6, 5) * 3; A(2, [1 4]) = 0; A(5, :) = 0;
C = floor(rand(6, 5) * 8); C(2, 1) = 0; C(2, 4) = 3; C(4, :) = 0; C(5, :) = 0;
out.dm_alpha = {A, A(1, :), [0.5 0.5], 1.5};
out.dm_counts = {C, C(1, :), [3 0], [2 3 4]};
out.dm = cell(1, numel(out.dm_alpha));
for k = 1:numel(out.dm_alpha)
  out.dm{k} = dirmultloglike(out.dm_alpha{k}, out.dm_counts{k});
end

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end
