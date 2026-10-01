function fx_search(outfile, seedoffset)
% Fixture for item 23 (L4-a): addnearmiss, choose_seedpairs, best_split,
% choose_node_split, with every randperm draw recorded through the shim
% (legacy/matlab/octave_shims/randperm.m, pass-through + FD_RANDPERM_LOG) so that Python can
% replay it (formdiscovery.rng.parse_queue).
%
% an    addnearmiss on seeded near-miss lists (lengths 1-8, -inf entries, ties, graphs
%       stored as strings): the epsilon early return, insertion at every position, and
%       the lower(1) error when no stored score is below the new one.
% ds    the data sets after runmodel's preprocessing (setrunps, scaledata, structcounts;
%       runmodel.m:27-95): the three feature demos (data stored) and the three
%       relational demos (Python loads them).
% sq    seeded growth sequences from makeemptygraph, one per (structure, data set, tying
%       mode) start in STARTS. At each step the candidate splits are listed as
%       structurefit.m:28-62 does: (component, occupied node, production) and, for
%       product graphs, (-1, node, vacant neighbour). Up to NCALL are picked at random
%       (a -1 candidate is always kept) and each runs choose_node_split at speed 5; at
%       step 1 the first pick also runs at speed 4, and at step 2 on feature data at
%       speed 3 (slow mode). The sequence continues from the best new graph. Each record
%       holds the inputs, the draws (logtext), ll, part1, part2, newgraph, and the seed
%       pairs from a separate choose_seedpairs call (sptext = its draws). A last,
%       crafted grid (6 objects in one end cell of a 3-cell chain, the middle vacant)
%       adds the high-level split of a node with more than 5 members.
% er    best_split with speeds that match no case (KI-1: 1, 2 and 54): the error text.
% bl    choose_node_split calls spied while re-running baseline runs with
%       run_baseline.m's settings and seed: chain x demo_chain_feat, tree x
%       demo_tree_feat, dirring x demo_ring_rel_bin and dirhierarchy x
%       demo_hierarchy_rel_bin (28 objects, >5-member seed pairs on relational data).
%       Every 5th call (at most 8 per run) is kept with its draws and the ps fields
%       that differ between calls. bl_ll holds each run's final score, which the test
%       compares with the committed baseline (the spy and the shim must not change it).
% SEEDOFFSET (default 0) shifts the rand('state') seeds of an and sq (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
sdir = fullfile(root, 'legacy', 'matlab', 'octave_shims');
addpath(mdir);
addpath(sdir);                 % prepended: the shim shadows the built-in
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd
ps0.showtruegraph = 0; ps0.showinferredgraph = 0; ps0.showbestsplit = 0;
ps0.showpreclean = 0; ps0.showpostclean = 0;
out = struct();
more off;
tmp = tempname(); mkdir(tmp);
lg = fullfile(tmp, 'log.txt');

MODES = [0 0 0 0; 0 0 1 0; 0 1 1 0; 0 0 0 1];   % none, exttie, alltie, prodtied
out.modes = MODES;

% --- an: addnearmiss --------------------------------------------------------------------
an = {};
rand('state', seedoffset + 101);
for t = 1:60
  L = 1 + floor(rand() * 8);
  sc = sort(round(rand(1, L) * 8) - 4, 'descend');   % integers: ties are common
  ninf = floor(rand() * (L + 1) * 0.5);
  sc(end - ninf + 1:end) = -inf;
  gr = arrayfun(@(k) sprintf('g%d', k), 1:L, 'UniformOutput', false);
  score = round(rand() * 10) - 5;
  if mod(t, 7) == 0, score = -inf; end
  if mod(t, 5) == 0, currscore = score + 1e-4; else, currscore = score + 1 + rand(); end
  r = struct('scores', sc, 'graphs', {gr}, 'score', score, 'currscore', currscore, ...
             'epsilon', 1e-3, 'err', '');
  try
    [s2, g2] = addnearmiss(sc, gr, sprintf('new%d', t), score, 'curr', currscore, 1e-3);
    r.out = s2; r.outg = g2;
  catch err
    r.err = err.message; r.out = []; r.outg = {};
  end
  an{end + 1} = r;
end
out.an = an;

% --- ds: data sets ----------------------------------------------------------------------
DS = [1 2 3 4 5 6];
dps = {}; ddata = {}; ds = {};
for k = 1:numel(DS)
  [ddata{k}, dps{k}] = prep(ps0, DS(k), mdir);
  r = struct('name', ps0.data{DS(k)}, 'type', dps{k}.runps.type);
  if ~strcmp(dps{k}.runps.type, 'rel'), r.data = ddata{k}; end
  ds{end + 1} = r;
end
out.ds = ds;

% --- sq: growth sequences ---------------------------------------------------------------
% {structure, data index into DS, mode, steps}
STARTS = {{'partition', 1, 1, 4}, {'chain', 1, 1, 5}, {'chain', 2, 2, 4}, ...
          {'ring', 2, 1, 5}, {'tree', 3, 3, 5}, {'tree', 1, 1, 4}, ...
          {'hierarchy', 3, 1, 4}, {'grid', 1, 1, 5}, {'grid', 2, 4, 4}, ...
          {'cylinder', 3, 1, 5}, {'connected', 2, 1, 3}, ...
          {'dirring', 4, 1, 4}, {'undirringnoself', 4, 1, 4}, {'partitionnoself', 4, 1, 3}, ...
          {'dirhierarchy', 5, 1, 3}, {'undirhierarchynoself', 5, 1, 2}, ...
          {'order', 6, 1, 4}, {'dirchainnoself', 6, 1, 3}, {'connected', 6, 1, 3}};
NCALL = 3;
sq = {};
out.sq_name = {};
for s = 1:numel(STARTS)
  st = STARTS{s};
  k = st{2};
  p = setmode(dps{k}, MODES(st{3}, :));
  p.runps.structname = st{1};
  out.sq_name{s} = sprintf('%s:%s:mode%d', st{1}, ps0.data{DS(k)}, st{3});
  rand('state', seedoffset + s);
  g = makeemptygraph(p);
  for step = 1:st{4}
    cands = candidates(g);
    pick = randperm_builtin(size(cands, 1));
    pick = pick(1:min(NCALL, numel(pick)));
    hl = find(cands(:, 1) < 0);
    if ~isempty(hl) && ~any(cands(pick, 1) < 0), pick(end) = hl(1); end
    best = -inf; bestg = [];
    for q = 1:numel(pick)
      speeds = 5;
      if q == 1 && step == 1, speeds = [5 4]; end
      if q == 1 && step == 2 && ~strcmp(p.runps.type, 'rel'), speeds = [5 3]; end
      cc = cands(pick(q), :);
      for sp = speeds
        p.speed = sp;
        r = struct('seq', s, 'step', step, 'graph', g, 'compind', cc(1), 'c', cc(2), ...
                   'pind', cc(3), 'speed', sp, 'data', k, 'mode', st{3}, 'err', '');
        fid = fopen(lg, 'w'); fclose(fid);
        randperm_config('', lg);
        try
          evalc('[ll, part1, part2, newgraph] = choose_node_split(g, cc(1), cc(2), cc(3), ddata{k}, p);');
          r.ll = ll; r.part1 = part1; r.part2 = part2; r.newgraph = newgraph;
        catch err
          r.err = err.message;
        end
        r.logtext = fileread(lg);
        % the seed pairs alone (choose_node_split skips them for one member)
        if sum(member_z(g, cc(1)) == cc(2)) >= 2
          fid = fopen(lg, 'w'); fclose(fid);
          r.seedpairs = choose_seedpairs(g, cc(1), cc(2), cc(3), p);
          r.sptext = fileread(lg);
        end
        sq{end + 1} = r;
        if sp == 5 && isempty(r.err) && r.ll > best, best = r.ll; bestg = r.newgraph; end
      end
    end
    if ~isstruct(bestg), break; end
    g = bestg;
  end
end
% crafted: a grid whose first chain has 3 nodes, with 6 objects at one end, none in the
% middle and 2 at the other end, so that both ends are high-level candidates next to a
% vacant cell and one of them has more than 5 members (choose_seedpairs.m:20-35 with
% compind = -1). All its candidates run at speed 5 (sequence numel(STARTS) + 1).
s = numel(STARTS) + 1;
out.sq_name{s} = 'grid:demo_chain_feat:mode1:crafted';
p = setmode(dps{1}, MODES(1, :)); p.runps.structname = 'grid'; p.speed = 5;
rand('state', seedoffset + s);
g = makeemptygraph(p);
evalc('g = split_node(g, 1, 1, 1, 1:4, 5:8, p);');
evalc('g = split_node(g, 1, 1, 1, 1:2, 3:4, p);');
deg = sum(g.components{1}.adjsym > 0, 1);
ends = find(deg == 1); mid = find(deg == 2);
g.components{1}.z = [ends(1) * ones(1, 6), ends(2) * ones(1, 2)];
g = combinegraphs(g, p);
cands = candidates(g);
for q = 1:size(cands, 1)
  cc = cands(q, :);
  r = struct('seq', s, 'step', 1, 'graph', g, 'compind', cc(1), 'c', cc(2), ...
             'pind', cc(3), 'speed', 5, 'data', 1, 'mode', 1, 'err', '');
  fid = fopen(lg, 'w'); fclose(fid);
  randperm_config('', lg);
  evalc('[ll, part1, part2, newgraph] = choose_node_split(g, cc(1), cc(2), cc(3), ddata{1}, p);');
  r.ll = ll; r.part1 = part1; r.part2 = part2; r.newgraph = newgraph;
  r.logtext = fileread(lg);
  if sum(member_z(g, cc(1)) == cc(2)) >= 2
    fid = fopen(lg, 'w'); fclose(fid);
    r.seedpairs = choose_seedpairs(g, cc(1), cc(2), cc(3), p);
    r.sptext = fileread(lg);
  end
  sq{end + 1} = r;
end
out.sq = sq;

% --- er: speeds that match no case (KI-1) -----------------------------------------------
er = {};
p = setmode(dps{1}, MODES(1, :)); p.runps.structname = 'chain';
g = makeemptygraph(p);
for sp = [1 2 54]
  p.speed = sp;
  r = struct('speed', sp, 'graph', g, 'err', '');
  try
    evalc('choose_node_split(g, 1, 1, 1, ddata{1}, p);');
  catch err
    r.err = err.message;
  end
  er{end + 1} = r;
end
out.er = er;
randperm_config();

% --- bl: spied baseline runs ------------------------------------------------------------
spydir = make_spy(mdir);
addpath(spydir, '-begin');
global SPY
runs = {{'feat', 2, 1}, {'feat', 6, 3}, {'rel', 17, 4}, {'rel', 21, 5}};
bl = {};
out.bl_run = {}; out.bl_ll = []; out.bl_ncalls = [];
for r = 1:numel(runs)
  SPY = struct('calls', {{}}, 'n', 0, 'log', lg);
  kind = runs{r}{1}; sind = runs{r}{2}; dind = runs{r}{3};
  randperm_config('', lg);
  out.bl_ll(r) = spied_run(mdir, fullfile(tmp, kind), kind, sind, dind);
  out.bl_run{r} = [ps0.structures{sind} ':' ps0.data{dind}];
  out.bl_ncalls(r) = SPY.n;
  for q = 1:numel(SPY.calls), SPY.calls{q}.run = r; bl{end + 1} = SPY.calls{q}; end
end
randperm_config();
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.bl = bl;
rmpath(sdir);                  % leave a shared (live-test) session with the built-in
clear('randperm');

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function p = randperm_builtin(n)
% selection draws for the fixture itself: not part of any logged call
p = builtin('randperm', n);
end

function z = member_z(g, compind)
if compind < 0, z = g.z; else, z = g.components{compind}.z; end
end

function cands = candidates(graph)
% structurefit.m:28-62: (i, c, pind) for occupied nodes and (-1, nd, nb) vacant moves
cands = zeros(0, 3);
for i = 1:graph.ncomp
  clegal = unique(graph.components{i}.z);
  for c = 1:graph.components{i}.nodecount
    if ismember(c, clegal)
      for pind = 1:graph.components{i}.prodcount
        cands(end + 1, :) = [i c pind];
      end
    end
  end
end
if graph.ncomp > 1
  nodecounts = hist(graph.z, 1:size(graph.adjcluster, 1));
  for nd = 1:size(graph.adjcluster, 1)
    if nodecounts(nd) > 1
      nbs = find(graph.adjclustersym(:, nd));
      for nbind = 1:length(nbs)
        if nodecounts(nbs(nbind)) == 0
          cands(end + 1, :) = [-1 nd nbs(nbind)];
        end
      end
    end
  end
end
end

function [data, ps] = prep(ps, dind, mdir)
% runmodel.m:27-95 without the graph initialisation
names = [];
olddir = pwd; cd(mdir); load(ps.dlocs{dind}); cd(olddir);
[nobjects, ps] = setrunps(data, dind, ps);
[data, ps] = scaledata(data, ps);
if isempty(names)
  for i = 1:nobjects, names{i} = num2str(i); end
end
ps.runps.names = names;   % choose_node_split.m:11 displays them
if ~isfield(ps, 'overrideSS'), ps.overrideSS = 0; end
ps.cleanstrong = 0;
ps = structcounts(nobjects, ps);
end

function p = setmode(p, m)
p.fixedall = m(1); p.fixedinternal = m(2); p.fixedexternal = m(3); p.prodtied = m(4);
end

function spydir = make_spy(mdir)
% choose_node_split_orig.m = choose_node_split.m renamed; choose_node_split.m = a spy
% that keeps every 5th call (<= 8 per run) with the randperm draws made inside it
spydir = tempname(); mkdir(spydir);
src = fileread(fullfile(mdir, 'choose_node_split.m'));
src = regexprep(src, '=\s*choose_node_split\(', '= choose_node_split_orig(', 'once');
fid = fopen(fullfile(spydir, 'choose_node_split_orig.m'), 'w');
fprintf(fid, '%s', src); fclose(fid);
spy = {
  'function [ll, part1, part2, newgraph] = choose_node_split(graph, compind, splitind, pind, data, ps)'
  'global SPY'
  'SPY.n = SPY.n + 1;'
  'keep = mod(SPY.n, 5) == 1 && numel(SPY.calls) < 8;'
  'if keep, fid = fopen(SPY.log, ''w''); fclose(fid); end'
  '[ll, part1, part2, newgraph] = choose_node_split_orig(graph, compind, splitind, pind, data, ps);'
  'if keep'
  '  q = struct(''speed'', ps.speed, ''fixedall'', ps.fixedall, ''fixedinternal'', ps.fixedinternal, ...'
  '    ''fixedexternal'', ps.fixedexternal, ''prodtied'', ps.prodtied, ''cleanstrong'', ps.cleanstrong, ...'
  '    ''structname'', ps.runps.structname);'
  '  SPY.calls{end + 1} = struct(''n'', SPY.n, ''graph'', graph, ''compind'', compind, ...'
  '    ''c'', splitind, ''pind'', pind, ''ps'', q, ''ll'', ll, ''part1'', part1, ''part2'', part2, ...'
  '    ''newgraph'', newgraph, ''logtext'', fileread(SPY.log));'
  'end'
  'end'};
fid = fopen(fullfile(spydir, 'choose_node_split.m'), 'w');
fprintf(fid, '%s\n', spy{:}); fclose(fid);
end

function ll = spied_run(mdir, outdir, kind, sind, dind)
% one run as in legacy/matlab/run_baseline.m (headless ps, rand('state', 1), relational runs with
% reloutsideinit 'overd'); output goes to OUTDIR
olddir = pwd;
cd(mdir); ps = defaultps(setps());   % setps builds ps.dlocs from pwd
ps.showtruegraph = 0; ps.showinferredgraph = 0; ps.showbestsplit = 0;
ps.showpreclean = 0; ps.showpostclean = 0;
if strcmp(kind, 'rel'), ps.reloutsideinit = 'overd'; end
if ~exist(outdir, 'dir'), mkdir(outdir); end
cd(outdir);
rand('state', 1);
try
  evalc('ll = runmodel(ps, sind, dind, 1);');
catch err
  cd(olddir); rethrow(err);
end
cd(olddir);
end
