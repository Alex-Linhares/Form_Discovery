function fx_rellike(outfile, seedoffset)
% Fixture for item 20 (L3-c): countmatrix, rellikebin, rellikefreqs, graph_like_rel (and
% graph_like's 'rel' dispatch).
%
% ri    graph_like_rel(data, g, ps) on relgraphinit graphs for the 24 ps.structures names
%       and the 4 domtree names on the 7 relational data sets (relbin: demo_ring_rel_bin,
%       demo_hierarchy_rel_bin, kularing, prisoners; relfreq: demo_order_rel_freq,
%       mangabeys, bushcabinet). Graphs come from z = 1:n, one cluster and two seeded
%       partitions, and a copy of the first partition graph with two objects unassigned
%       (z = -1). Each record stores logI, the returned graph, countmatrix(data.R, g) and
%       graph_like's logI, or Octave's error message. This covers every dir/undir/noself
%       variant (the diagonal self-link and symmetrisation branches, l.107-121) and the
%       filloutrelgraph types (l.8-13) that relgraphinit can build.
% sq    graphs from seeded split_node sequences (makeemptygraph, 6 steps) on the 7 data
%       sets for the order, connected and domtree names (relgraphinit cannot build
%       connected or domtree graphs) and a few others; stored per step as ri.
% sy    the same on seeded random relations (binary and counts, n = 6 and 9), run as
%       relbin and as relfreq, with an R that has self links (nonzero diagonal) and one
%       with a NaN entry (the nanscore error, l.159-161).
% pv    a subset of ri graphs under non-default ps.edgesumsteps / edgeoffset /
%       edgesumlambda.
% gh    every bestgraph of the 54 relational baseline growth histories, scored with
%       graph_like_rel and graph_prior (gh_file names the file; bgll the stored
%       bestgraphlls entry).
% rb/rf direct rellikebin / rellikefreqs calls on seeded random count/adjacency/size
%       vectors (including an adjacency with no ones, the isempty(ys) branch).
% rd    the 'reldom' branch (l.22-101, "not currently used"): seeded random 3-D R
%       (yobs <= nobs), lowdiag 0 and 1, on relgraphinit graphs including two-cluster
%       one-edge graphs; and the 'data not lower diagonal!' error.
% bl    graph_like_rel calls spied during four baseline runs (run_baseline.m's settings;
%       every 20th call, <= 12 per run) with inputs and outputs. bl_ll holds each run's
%       final score (compared with the committed baseline), bl_n the number of calls.
% SEEDOFFSET (default 0) shifts the rand('state') seeds (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'matlab', 'formdiscovery1.0');
fxdir = fullfile(root, 'tests', 'fixtures');
addpath(mdir);
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd
out = struct();
more off;

names = [ps0.structures, {'domtree', 'dirdomtreenoself', 'undirdomtree', 'undirdomtreenoself'}];
out.names = names;
relsets = {'demo_ring_rel_bin', 'demo_hierarchy_rel_bin', 'demo_order_rel_freq', ...
           'mangabeys', 'bushcabinet', 'kularing', 'prisoners'};
out.relsets = relsets;
datas = {}; dps = {};
for d = 1:numel(relsets)
  dind = find(strcmp(ps0.data, relsets{d}));
  [datas{d}, dps{d}] = prep(ps0, dind);
end

% --- relgraphinit graphs on the data sets ---------------------------------------------
rand('state', seedoffset + 1);
ri = {};
for d = 1:numel(relsets)
  ri = [ri, score_inputs(datas{d}, dps{d}, names, d, '')];
end
out.ri = ri;

% --- split_node sequences (types relgraphinit cannot build) ---------------------------
sqnames = {'order', 'ordernoself', 'connected', 'connectednoself', 'domtree', ...
           'dirdomtreenoself', 'undirdomtree', 'undirdomtreenoself', 'partition', ...
           'undirchain', 'undirring', 'undirhierarchynoself', 'dirhierarchy'};
out.sqnames = sqnames;
sq = {};
for d = 1:numel(relsets)
  for s = 1:numel(sqnames)
    p = dps{d}; p.runps.structname = sqnames{s};
    g = makeemptygraph(p);
    rand('state', seedoffset + 100 * d + s);
    for step = 1:6
      comp = g.components{1};
      pind = 1 + floor(rand() * comp.prodcount);
      cands = [];
      for c = 1:comp.nodecount
        if sum(comp.z == c) >= 2, cands(end + 1) = c; end
      end
      if isempty(cands), break; end
      c = cands(1 + floor(rand() * numel(cands)));
      members = find(comp.z == c);
      [~, o] = sort(rand(1, numel(members)));
      members = members(o);
      m = max(1, 1 + floor(rand() * (numel(members) - 1)));
      evalc('[g2, c1, c2] = split_node(g, 1, c, pind, members(1:m), members(m + 1:end), p);');
      if ~isstruct(g2), continue; end
      g = g2;
      r = struct('data', d, 'name', sqnames{s}, 'step', step, 'graph', g, 'err', '', ...
                 'logI', [], 'out', [], 'counts', [], 'gllogI', []);
      try
        r.counts = countmatrix(datas{d}.R, g);
        [r.logI, r.out] = graph_like_rel(datas{d}, g, p);
        r.gllogI = graph_like(datas{d}, g, p);
      catch err
        r.err = err.message;
      end
      sq{end + 1} = r;
    end
  end
end
out.sq = sq;

% --- seeded random relations ----------------------------------------------------------
rand('state', seedoffset + 2);
sy = {};
Rsy = {};
for n = [6 9]
  Rsy{end + 1} = double(rand(n) < 0.35) .* (1 - eye(n));
  Rsy{end + 1} = floor(rand(n) * 5) .* (1 - eye(n));
end
Rsy{end + 1} = double(rand(7) < 0.4);           % self links
Rsy{end + 1} = floor(rand(7) * 4);              % self links, counts
Rbad = double(rand(6) < 0.4); Rbad(2, 3) = NaN; % nanscore
Rsy{end + 1} = Rbad;
out.Rsy = Rsy;
for q = 1:numel(Rsy)
  for t = {'relbin', 'relfreq'}
    data = struct('R', Rsy{q}, 'type', t{1}, 'nobj', size(Rsy{q}, 1));
    p = ps0; p.runps.type = 'rel'; p.runps.nobjects = data.nobj;
    sy = [sy, score_inputs(data, p, names, q, t{1})];
  end
end
out.sy = sy;

% --- non-default hyperparameter grids -------------------------------------------------
pvs = [5 -5 2; 10 -3 2; 7 -5 1.5; 3 0 3];
out.pvs = pvs;
pv = {};
for q = 1:7:numel(ri)
  r = ri{q};
  if ~isempty(r.err) || ~isstruct(r.graph), continue; end
  for v = 1:size(pvs, 1)
    p = dps{r.data};
    p.edgesumsteps = pvs(v, 1); p.edgeoffset = pvs(v, 2); p.edgesumlambda = pvs(v, 3);
    s = struct('ri', q, 'pv', v, 'err', '', 'logI', []);
    try
      s.logI = graph_like_rel(datas{r.data}, r.graph, p);
    catch err
      s.err = err.message;
    end
    pv{end + 1} = s;
  end
end
out.pv = pv;

% --- baseline growth histories --------------------------------------------------------
d = fullfile(fxdir, 'baseline', 'rel', 'results');
gh = {};
out.gh_file = {};
st = dir(d);
for a = 1:numel(st)
  if st(a).name(1) == '.', continue; end
  sd = dir(fullfile(d, st(a).name));
  for b = 1:numel(sd)
    if sd(b).name(1) == '.', continue; end
    fs = dir(fullfile(d, st(a).name, sd(b).name, 'growthhistory*.mat'));
    for c = 1:numel(fs)
      out.gh_file{end + 1} = [st(a).name '/' sd(b).name '/' fs(c).name];
      f = numel(out.gh_file);
      di = find(strcmp(relsets, sd(b).name(1:end - 1)));
      L = load(fullfile(d, st(a).name, sd(b).name, fs(c).name));
      for k = 1:numel(L.bestgraph)
        g = L.bestgraph{k};
        if ~isstruct(g), continue; end
        p = dps{di}; p.runps.structname = g.type;
        r = struct('file', f, 'depth', k, 'data', di, 'graph', g, ...
                   'bgll', L.bestgraphlls(k), 'err', '', 'logI', [], 'out', [], 'prior', []);
        try
          [r.logI, r.out] = graph_like_rel(datas{di}, g, p);
          r.prior = graph_prior(r.out, p);
        catch err
          r.err = err.message;
        end
        gh{end + 1} = r;
      end
    end
  end
end
out.gh = gh;

% --- rellikebin / rellikefreqs directly -----------------------------------------------
rand('state', seedoffset + 3);
rb = {}; rf = {};
p = ps0;
mags = p.edgesumlambda .^ (p.edgeoffset + 1:p.edgeoffset + p.edgesumsteps);
thetas = (1:10) / 10 - 1 / 20;
ep = (6:10) / 10 - 1 / 20;
[ae, be] = makehyps(ep, mags);
for q = 1:12
  k = 2 + floor(rand() * 5);
  sizes = floor(rand(k) * 6) + 1; sizes(1:k + 1:end) = floor(rand(1, k) * 3);
  counts = floor(rand(k) .* (sizes + 1));
  adj = double(rand(k) < 0.4);
  if q == 1, adj = zeros(k); end
  if q == 2, adj = ones(k); end
  rb{end + 1} = struct('countvec', counts(:), 'adjvec', adj(:), 'sizevec', sizes(:), ...
                       'll', rellikebin(counts(:), adj(:), sizes(:), mags', thetas'));
  fc = floor(rand(k) * 30) .* (sizes > 0);
  rf{end + 1} = struct('countvec', fc(:), 'adjvec', adj(:), 'sizevec', sizes(:), ...
                       'll', rellikefreqs(fc(:)', adj(:)', sizes(:)', ae', be'));
end
out.rb = rb; out.rf = rf; out.mags = mags; out.thetas = thetas; out.ae = ae; out.be = be;

% --- reldom ---------------------------------------------------------------------------
rand('state', seedoffset + 4);
rd = {};
rdnames = {'partition', 'dirchain', 'dirchainnoself', 'undirchain', 'order', 'dirring', ...
           'dirhierarchy', 'connected', 'domtree'};
Rrd = {};
for n = [6 8]
  for lowdiag = 0:1
    N = floor(rand(n) * 5);
    if lowdiag, N(1:n + 1:end) = 0; end
    Y = floor(rand(n) .* (N + 1));
    R = cat(3, Y, N);
    Rrd{end + 1} = struct('R', R, 'lowdiag', lowdiag);
    data = struct('R', R, 'type', 'reldom', 'nobj', n, 'lowdiag', lowdiag);
    zs = {ones(1, n), [ones(1, 3), 2 * ones(1, n - 3)]};
    for rep = 1:2
      k = 2 + floor(rand() * (n - 2));
      [~, ~, z] = unique(1 + floor(rand(1, n) * k));
      zs{end + 1} = z(:)';
    end
    zs{end + 1} = 1:n;
    for t = 1:numel(rdnames)
      p = ps0; p.runps.structname = rdnames{t}; p.runps.nobjects = n; p.runps.type = 'rel';
      for zi = 1:numel(zs)
        r = struct('R', numel(Rrd), 'name', rdnames{t}, 'z', zs{zi}, 'graph', 0, ...
                   'err', '', 'logI', [], 'out', []);
        try
          r.graph = relgraphinit(sum(R, 3), zs{zi}, p);
        catch err
          continue
        end
        try
          [r.logI, r.out] = graph_like_rel(data, r.graph, p);
        catch err
          r.err = err.message;
        end
        rd{end + 1} = r;
      end
    end
  end
end
% lowdiag with a nonzero diagonal count
N = floor(rand(5) * 3) + 1; R = cat(3, zeros(5), N);
Rrd{end + 1} = struct('R', R, 'lowdiag', 1);
p = ps0; p.runps.structname = 'partition'; p.runps.nobjects = 5; p.runps.type = 'rel';
g = relgraphinit(N, [1 1 2 2 2], p);
r = struct('R', numel(Rrd), 'name', 'partition', 'z', [1 1 2 2 2], 'graph', g, ...
           'err', '', 'logI', [], 'out', []);
try
  [r.logI, r.out] = graph_like_rel(struct('R', R, 'type', 'reldom', 'nobj', 5, 'lowdiag', 1), g, p);
catch err
  r.err = err.message;
end
rd{end + 1} = r;
out.Rrd = Rrd;
out.rd = rd;
% unknown data type
try
  graph_like_rel(struct('R', eye(3), 'type', 'relxyz', 'nobj', 3), g, p);
  out.unknown_err = '';
catch err
  out.unknown_err = err.message;
end

% --- spied baseline runs --------------------------------------------------------------
spydir = make_spy(mdir);
addpath(spydir, '-begin');
global SPY
tmp = tempname(); mkdir(tmp);
bl = {};
runs = {{'dirring', 4}, {'undirhierarchy', 5}, {'order', 6}, {'partitionnoself', 6}};
out.bl_run = {}; out.bl_ll = []; out.bl_n = [];
for r = 1:numel(runs)
  SPY = struct('calls', {{}}, 'n', 0);
  sind = find(strcmp(ps0.structures, runs{r}{1}));
  out.bl_ll(r) = spied_run(mdir, tmp, sind, runs{r}{2});
  out.bl_run{r} = [runs{r}{1} ':' ps0.data{runs{r}{2}}];
  out.bl_n(r) = SPY.n;
  for q = 1:numel(SPY.calls), SPY.calls{q}.run = r; bl{end + 1} = SPY.calls{q}; end
end
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.bl = bl;

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function recs = score_inputs(data, ps, names, src, dtype)
% relgraphinit graphs (z = 1:n, one cluster, two seeded partitions, one with two
% unassigned objects) for every name, scored by graph_like_rel
n = data.nobj;
zs = {1:n, ones(1, n)};
for rep = 1:2
  k = 2 + floor(rand() * (n - 2));
  [~, ~, z] = unique(1 + floor(rand(1, n) * k));
  zs{end + 1} = z(:)';
end
Rinit = data.R; Rinit(isnan(Rinit)) = 0;
recs = {};
for t = 1:numel(names)
  p = ps; p.runps.structname = names{t};
  for zi = 1:5
    r = struct('data', src, 'dtype', dtype, 'name', names{t}, 'zkind', zi, 'graph', 0, ...
               'err', '', 'logI', [], 'out', [], 'counts', [], 'gllogI', []);
    try
      if zi <= 4
        r.graph = relgraphinit(Rinit, zs{zi}, p);
      else
        r.graph = relgraphinit(Rinit, zs{3}, p);
        r.graph.z([1, n]) = -1;
      end
    catch err
      r.err = ['init: ' err.message];
      recs{end + 1} = r;
      continue
    end
    try
      r.counts = countmatrix(data.R, r.graph);
      [r.logI, r.out] = graph_like_rel(data, r.graph, p);
      r.gllogI = graph_like(data, r.graph, p);
    catch err
      r.err = err.message;
    end
    recs{end + 1} = r;
  end
end
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

function spydir = make_spy(mdir)
% graph_like_rel_orig.m = graph_like_rel.m renamed; graph_like_rel.m = a spy logging
% every 20th call (<= 12 per run)
spydir = tempname(); mkdir(spydir);
src = fileread(fullfile(mdir, 'graph_like_rel.m'));
src = regexprep(src, 'function \[logI graph\] = graph_like_rel\(', ...
                'function [logI graph] = graph_like_rel_orig(', 'once');
fid = fopen(fullfile(spydir, 'graph_like_rel_orig.m'), 'w'); fprintf(fid, '%s', src); fclose(fid);
spy = {
  'function [logI graph] = graph_like_rel(data, graph, ps)'
  'global SPY'
  'ingraph = graph;'
  '[logI graph] = graph_like_rel_orig(data, graph, ps);'
  'SPY.n = SPY.n + 1;'
  'if mod(SPY.n, 20) == 1 && numel(SPY.calls) < 12'
  '  SPY.calls{end + 1} = struct(''n'', SPY.n, ''graph'', ingraph, ''dtype'', data.type, ...'
  '    ''R'', data.R, ''logI'', logI, ''out'', graph);'
  'end'
  'end'};
fid = fopen(fullfile(spydir, 'graph_like_rel.m'), 'w');
fprintf(fid, '%s\n', spy{:}); fclose(fid);
end

function ll = spied_run(mdir, outdir, sind, dind)
% one relational run as in matlab/run_baseline.m (headless ps, rand('state', 1),
% reloutsideinit 'overd'); output goes to OUTDIR
olddir = pwd;
cd(mdir); ps = defaultps(setps());   % setps builds ps.dlocs from pwd
ps.showtruegraph = 0; ps.showinferredgraph = 0; ps.showbestsplit = 0;
ps.showpreclean = 0; ps.showpostclean = 0;
ps.reloutsideinit = 'overd';
cd(outdir);
rand('state', 1);
try
  evalc('ll = runmodel(ps, sind, dind, 1);');
catch err
  cd(olddir); rethrow(err);
end
cd(olddir);
end
