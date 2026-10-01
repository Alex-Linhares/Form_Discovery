function fx_truegraphs(outfile)
% Fixture for item 21 (M3 checkpoint): the true graph stored in each demo data set,
% scored by graph_like in fast mode (ps.fast = 1: the stored weights) and in slow mode
% (ps.fast = 0: fminunc + Laplace, graph_like_conn.m:35-110).
%
% fe    feature demos (demo_chain_feat, demo_ring_feat, demo_tree_feat). The file holds
%       the full adj/W over objcount objects plus the cluster nodes, and sigma. The graph
%       is built with the model's own code: makeemptygraph(ps) for the file's structure,
%       then one component with z(i) = the cluster node object i hangs from,
%       adj = triu of the cluster block (only adjsym/Wsym reach the feature likelihood),
%       W = the cluster weights on those edges, illegal = the cluster nodes holding no
%       object (tree internal nodes), leaflengths = the object-to-cluster weights,
%       extlen/intlen = the (unique) leaf / cluster weight, then combinegraphs.
%       Each graph is scored in tying modes none, exttie (fixedexternal) and alltie
%       (fixedinternal + fixedexternal), on the data after runmodel's preprocessing.
% re    relational demos (demo_ring_rel_bin, demo_hierarchy_rel_bin, demo_order_rel_freq).
%       The file's graph (adjcluster, adj, objcount, z) with graph.type set to each
%       relational form of the generating family (ring: dirring, dirringnoself, undirring,
%       undirringnoself; hierarchy: dirhierarchy, dirhierarchynoself, undirhierarchy,
%       undirhierarchynoself; order: order, ordernoself). Relational scoring has no
%       optimiser, so fast and slow mode are the same computation; both are stored.
% Each record stores the input graph, logI and the returned graph for fast and slow mode,
% graph_prior, and the error message if any.
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
addpath(mdir);
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd
out = struct();
more off;

MODES = [0 0 0 0; 0 0 1 0; 0 1 1 0];   % fixedall fixedinternal fixedexternal prodtied
MODENAMES = {'none', 'exttie', 'alltie'};
out.modes = MODES;
out.modenames = MODENAMES;

% --- feature demos --------------------------------------------------------------------
fe = {};
for dind = 1:3
  name = ps0.data{dind};
  T = load(ps0.dlocs{dind});
  [data, p] = prep(ps0, dind);
  p.runps.structname = T.structure;
  g = truefeatgraph(T, p);
  for mi = 1:size(MODES, 1)
    q = setmode(p, MODES(mi, :));
    r = struct('name', name, 'structure', T.structure, 'mode', mi, 'graph', g, ...
               'data', data, 'err', '', 'fast', [], 'fastgraph', [], 'slow', [], ...
               'slowgraph', [], 'prior', []);
    try
      q.fast = 1; [r.fast, r.fastgraph] = graph_like(data, g, q);
      q.fast = 0; [r.slow, r.slowgraph] = graph_like(data, g, q);
      r.prior = graph_prior(g, q);
    catch err
      r.err = err.message;
    end
    fe{end + 1} = r;
  end
end
out.fe = fe;

% --- relational demos -----------------------------------------------------------------
FORMS = struct('demo_ring_rel_bin', {{'dirring', 'dirringnoself', 'undirring', ...
                                      'undirringnoself'}}, ...
               'demo_hierarchy_rel_bin', {{'dirhierarchy', 'dirhierarchynoself', ...
                                           'undirhierarchy', 'undirhierarchynoself'}}, ...
               'demo_order_rel_freq', {{'order', 'ordernoself'}});
re = {};
for dind = 4:6
  name = ps0.data{dind};
  T = load(ps0.dlocs{dind});
  [data, p] = prep(ps0, dind);
  forms = FORMS.(name);
  for f = 1:numel(forms)
    g = T.graph; g.type = forms{f};
    q = p; q.runps.structname = forms{f};
    r = struct('name', name, 'structure', forms{f}, 'graph', g, 'err', '', 'fast', [], ...
               'fastgraph', [], 'slow', [], 'slowgraph', [], 'prior', []);
    try
      q.fast = 1; [r.fast, r.fastgraph] = graph_like(data, g, q);
      q.fast = 0; [r.slow, r.slowgraph] = graph_like(data, g, q);
      r.prior = graph_prior(g, q);
    catch err
      r.err = err.message;
    end
    re{end + 1} = r;
  end
end
out.re = re;
save('-v7', outfile, '-struct', 'out');
end

function g = truefeatgraph(T, ps)
% the true graph of a feature demo file, built with makeemptygraph + combinegraphs
n = double(T.objcount);
A = double(T.adj); W = double(T.W);
k = size(A, 1) - n;
z = zeros(1, n); lw = zeros(1, n);
for i = 1:n
  c = find(A(i, n + 1:end));
  if numel(c) ~= 1, error('object %d is not a leaf', i); end
  z(i) = c; lw(i) = W(n + c, i);
end
Ac = triu(A(n + 1:end, n + 1:end));
Wc = W(n + 1:end, n + 1:end) .* Ac;
g = makeemptygraph(ps);
g.sigma = double(T.sigma);
g.z = z;
g.leaflengths = lw;
g.extlen = unique(lw);
g.intlen = unique(Wc(Ac > 0));
if numel(g.extlen) ~= 1 || numel(g.intlen) ~= 1, error('weights are not tied'); end
c = g.components{1};
c.adj = Ac; c.W = Wc;
c.adjsym = double(Ac | Ac'); c.Wsym = Wc + Wc';
c.nodecount = k; c.edgecount = nnz(Ac); c.edgecountsym = nnz(Ac);
c.z = z;
c.illegal = setdiff(1:k, z);
g.components{1} = c;
g = combinegraphs(g, ps);
end

function p = setmode(p, m)
p.fixedall = m(1); p.fixedinternal = m(2); p.fixedexternal = m(3); p.prodtied = m(4);
end

function [data, ps] = prep(ps, dind)
% runmodel.m:27-95 without the graph initialisation
load(ps.dlocs{dind});
[nobjects, ps] = setrunps(data, dind, ps);
[data, ps] = scaledata(data, ps);
if ~isfield(ps, 'overrideSS'), ps.overrideSS = 0; end
ps.cleanstrong = 0;
ps = structcounts(nobjects, ps);
end
