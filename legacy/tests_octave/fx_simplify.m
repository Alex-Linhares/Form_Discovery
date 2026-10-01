function fx_simplify(outfile, seedoffset)
% Fixture for item 13 (L2-a3): simplify_graph (+redundantinds), subtreeattach.
%
% Every simplify record holds the input graph, the ps fields simplify_graph reads
% (cleanstrong, runps.type, fixedall/fixedinternal/fixedexternal, prodtied) and the output.
% gh_*  every bestgraph of the 73 baseline growth histories, simplified with cleanstrong 0
%       and 1 (runps.type from the baseline: feat or rel).
% sq_*  seeded sequences: makeemptygraph (12 objects) for the 26 single-component names and
%       grid/cylinder (prodtied 0 and 1), 7 seeded split_node steps with random weights
%       (as in fx_split.m). After steps 3 and 7 the graph is simplified raw, after moving
%       all members of one node to another legal node, and after emptying two nodes into a
%       third, each under the configs cs0/feat, cs1/feat, cs0/rel and (trees) cs0/fixedall,
%       cs0/fixedinternal. For the tree and hierarchy families, subtreeattach is then called
%       on seeded regrafts (objflag 0: a cluster node onto an edge/node as spr>makers would
%       choose; objflag 1: an object; plus the parentless-root no-op) and its output is
%       simplified with cleanstrong 0 and 1. 'dirdomtreenoself' is not in subtreeattach's
%       list, so it records the 'unexpected structure' error.
% bl_*  simplify_graph / subtreeattach calls captured by spies while re-running baseline
%       runs with run_baseline.m's settings and seed: chain x demo_chain_feat,
%       ring x demo_ring_feat, tree x demo_chain_feat and demo_tree_feat, and the four
%       dirhierarchy..undirhierarchynoself structures x demo_hierarchy_rel_bin. Per run and
%       cleanstrong value the first 10 calls that change the graph and the first 2 that do
%       not are kept, and the first 6 subtreeattach calls per objflag. bl_ll holds each
%       run's final score, which the test compares with the committed baseline.
% SEEDOFFSET (default 0) shifts the rand('state') seeds of the sequences (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
addpath(mdir);
ps = defaultps(setps());
out = struct();
more off;

% --- growth histories -----------------------------------------------------------------
gh = {};
files = {};
for kind = {'feat', 'rel'}
  d = fullfile(root, 'tests', 'fixtures', 'baseline', kind{1}, 'results');
  st = dir(d);
  for a = 1:numel(st)
    if st(a).name(1) == '.', continue; end
    sd = dir(fullfile(d, st(a).name));
    for b = 1:numel(sd)
      if sd(b).name(1) == '.', continue; end
      fs = dir(fullfile(d, st(a).name, sd(b).name, 'growthhistory*.mat'));
      for c = 1:numel(fs)
        files{end + 1} = {kind{1}, fullfile(d, st(a).name, sd(b).name, fs(c).name), ...
                          [st(a).name '/' sd(b).name '/' fs(c).name]};
      end
    end
  end
end
out.gh_file = {};
for f = 1:numel(files)
  out.gh_file{f} = files{f}{3};
  L = load(files{f}{2});
  for k = 1:numel(L.bestgraph)
    g = L.bestgraph{k};
    if ~isstruct(g), continue; end
    for cs = 0:1
      p = cfg(ps, cs, files{f}{1}, '', 0);
      gh{end + 1} = rec(g, p, simplify_graph(g, p));
      gh{end}.file = f;
    end
  end
end
out.gh = gh;

% --- seeded sequences -----------------------------------------------------------------
names = [ps.structures, {'domtree', 'dirdomtreenoself', 'undirdomtree', 'undirdomtreenoself'}];
names = names(~strcmp(names, 'grid') & ~strcmp(names, 'cylinder'));
starts = {};
for t = 1:numel(names), starts{end + 1} = {names{t}, 0}; end
for t = {'grid', 'cylinder'}
  for pt = 0:1, starts{end + 1} = {t{1}, pt}; end
end
sattach = {'tree', 'hierarchy', 'dirhierarchy', 'domtree', 'dirhierarchynoself', ...
           'domtreenoself', 'undirhierarchy', 'undirhierarchynoself', 'undirdomtree', ...
           'undirdomtreenoself', 'dirdomtreenoself'};
sq = {}; st_ = {};
out.sq_name = {};
for s = 1:numel(starts)
  name = starts{s}{1}; pt = starts{s}{2};
  out.sq_name{s} = sprintf('%s:prodtied%d', name, pt);
  p = ps; p.prodtied = pt; p.runps.structname = name; p.runps.nobjects = 12;
  p.runps.type = 'feat';
  g = makeemptygraph(p);
  rand('state', seedoffset + s);
  for step = 1:7
    g = randweights(g);
    i = 1 + (g.ncomp > 1) * (rand() > 0.5);
    comp = g.components{i};
    pind = 1 + floor(rand() * comp.prodcount);
    cands = occnodes(comp);
    c = cands(1 + floor(rand() * numel(cands)));
    members = find(comp.z == c);
    [~, o] = sort(rand(1, numel(members)));
    members = members(o);
    if numel(members) >= 2
      m = 1 + floor(rand() * (numel(members) - 1));
    else
      m = 1;
    end
    [g2, c1, c2] = quiet_split(g, i, c, pind, members(1:m), members(m + 1:end), p);
    if isstruct(g2), g = g2; end
    if step ~= 3 && step ~= 7, continue; end
    % dirty variants
    g = randweights(g);
    variants = {g};
    i = 1 + (g.ncomp > 1) * (rand() > 0.5);
    comp = g.components{i};
    occ = occnodes(comp);
    legal = setdiff(1:comp.nodecount, comp.illegal);
    if numel(legal) >= 2
      src = occ(1 + floor(rand() * numel(occ)));
      tg = legal(legal ~= src); tg = tg(1 + floor(rand() * numel(tg)));
      h = g; h.components{i}.z(h.components{i}.z == src) = tg;
      variants{end + 1} = prodw(combinegraphs(h, p));
    end
    if numel(occ) >= 3
      [~, o] = sort(rand(1, numel(occ)));
      h = g; h.components{i}.z(ismember(h.components{i}.z, occ(o(1:2)))) = occ(o(3));
      variants{end + 1} = prodw(combinegraphs(h, p));
    end
    cfgs = {{0, 'feat', ''}, {1, 'feat', ''}, {0, 'rel', ''}};
    if strcmp(name, 'tree')
      cfgs = [cfgs, {{0, 'feat', 'fixedall'}, {0, 'feat', 'fixedinternal'}}];
    end
    for v = 1:numel(variants)
      for q = 1:numel(cfgs)
        pp = cfg(p, cfgs{q}{1}, cfgs{q}{2}, cfgs{q}{3}, pt);
        sq{end + 1} = rec(variants{v}, pp, simplify_graph(variants{v}, pp));
        sq{end}.seq = s; sq{end}.step = step; sq{end}.variant = v;
      end
    end
    % regrafts
    if ~any(strcmp(name, sattach)), continue; end
    g.leaflengths = 0.5 + rand(1, g.objcount);
    g = combinegraphs(g, p);
    comp = g.components{1};
    adj = comp.adj; n = comp.nodecount;
    tries = {};
    % objflag 0: cluster nodes with a parent
    haspar = find(sum(adj, 1) > 0);
    desc = find_descendants(adj);
    [~, o] = sort(rand(1, numel(haspar)));
    for j = haspar(o(1:min(3, end)))
      jpar = find(adj(:, j));
      jds = [j, desc{j}];
      if strcmp(comp.type, 'tree')
        e = adj; e(jds, jds) = 0;
        [rs, cs] = find(e);
        keep = find(sum([rs, cs] == jpar(1), 2) == 0);
        rs = rs(keep); cs = cs(keep);
      else
        rs = setdiff(1:n, [jds, jpar(:)']); cs = rs;
      end
      if isempty(rs), continue; end
      e = 1 + floor(rand() * numel(rs));
      tries{end + 1} = {j, rs(e), cs(e), 0};
    end
    % objflag 0 on a parentless node: no-op
    nopar = find(sum(adj, 1) == 0);
    tries{end + 1} = {nopar(1), 1, 1, 0};
    % objflag 1: objects
    for k = 1:2
      j = 1 + floor(rand() * g.objcount);
      if strcmp(comp.type, 'tree')
        [rs, cs] = find(adj);
      else
        rs = setdiff(1:n, comp.z(j)); cs = rs;
      end
      if isempty(rs), continue; end
      e = 1 + floor(rand() * numel(rs));
      tries{end + 1} = {j, rs(e), cs(e), 1};
    end
    for t = 1:numel(tries)
      a = tries{t};
      r = struct('seq', s, 'step', step, 'graph', g, 'j', a{1}, 'edgep', a{2}, ...
                 'edgec', a{3}, 'comp', 1, 'objflag', a{4}, 'prodtied', pt, 'err', '', ...
                 'out', 0, 'simp0', 0, 'simp1', 0);
      try
        r.out = subtreeattach(g, a{1}, a{2}, a{3}, 1, p, 'objflag', a{4});
        r.simp0 = simplify_graph(r.out, cfg(p, 0, 'feat', '', pt));
        r.simp1 = simplify_graph(r.out, cfg(p, 1, 'feat', '', pt));
      catch err
        r.err = err.message;
      end
      st_{end + 1} = r;
    end
  end
end
out.sq = sq; out.st = st_;

% --- spied baseline runs --------------------------------------------------------------
spydir = make_spies(mdir);
addpath(spydir, '-begin');
global SPY
runs = {{'feat', 2, 1}, {'feat', 4, 2}, {'feat', 6, 1}, {'feat', 6, 3}};
for sind = 21:24, runs{end + 1} = {'rel', sind, 5}; end
tmp = tempname(); mkdir(tmp);
bl_sg = {}; bl_st = {};
out.bl_run = {}; out.bl_ll = []; out.bl_sind = []; out.bl_dind = [];
for r = 1:numel(runs)
  SPY = struct('sg', {{}}, 'st', {{}}, 'nch', [0 0], 'nun', [0 0], 'nst', [0 0]);
  kind = runs{r}{1}; sind = runs{r}{2}; dind = runs{r}{3};
  out.bl_ll(r) = spied_run(mdir, fullfile(tmp, kind), kind, sind, dind);
  out.bl_run{r} = [ps.structures{sind} ':' ps.data{dind}];
  out.bl_sind(r) = sind; out.bl_dind(r) = dind;
  for q = 1:numel(SPY.sg), SPY.sg{q}.run = r; bl_sg{end + 1} = SPY.sg{q}; end
  for q = 1:numel(SPY.st), SPY.st{q}.run = r; bl_st{end + 1} = SPY.st{q}; end
end
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.bl_sg = bl_sg; out.bl_st = bl_st;

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function p = cfg(p, cs, rtype, fixed, pt)
p.cleanstrong = cs; p.runps.type = rtype; p.prodtied = pt;
p.fixedall = 0; p.fixedinternal = 0; p.fixedexternal = 0;
if ~isempty(fixed), p.(fixed) = 1; end
end

function r = rec(g, p, gout)
r = struct('graph', g, 'cleanstrong', p.cleanstrong, 'rtype', p.runps.type, ...
           'fixedall', p.fixedall, 'fixedinternal', p.fixedinternal, ...
           'fixedexternal', p.fixedexternal, 'prodtied', p.prodtied, 'out', gout);
end

function g = randweights(g)
for j = 1:g.ncomp
  g.components{j}.W = g.components{j}.adj .* (0.5 + rand(size(g.components{j}.adj)));
end
g.Wcluster = g.adjcluster .* (0.5 + rand(size(g.adjcluster)));
end

function g = prodw(g)
% combinegraphs without origgraph rebuilds Wcluster from W; give products distinct
% cluster weights again so simplify_graph's origgraph copy moves visible values
if g.ncomp > 1
  g.Wcluster = g.adjcluster .* (0.5 + rand(size(g.adjcluster)));
end
end

function cands = occnodes(comp)
cands = [];
for c = 1:comp.nodecount
  if any(comp.z == c), cands(end + 1) = c; end
end
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

function [g, c1, c2] = quiet_split(g, i, c, pind, part1, part2, p)
% split_node prints the production name; keep the log quiet
evalc('[g, c1, c2] = split_node(g, i, c, pind, part1, part2, p);');
end

function spydir = make_spies(mdir)
% <f>_orig.m = <f>.m with the function renamed; <f>.m = a spy that logs capped calls
spydir = tempname(); mkdir(spydir);
for f = {'simplify_graph', 'subtreeattach'}
  src = fileread(fullfile(mdir, [f{1} '.m']));
  src = regexprep(src, ['=\s*' f{1} '\('], ['= ' f{1} '_orig('], 'once');
  fid = fopen(fullfile(spydir, [f{1} '_orig.m']), 'w'); fprintf(fid, '%s', src); fclose(fid);
end
spy.simplify_graph = {
  'function graph = simplify_graph(graph, ps)'
  'global SPY'
  'gin = graph;'
  'graph = simplify_graph_orig(graph, ps);'
  'k = ps.cleanstrong + 1; ch = ~isequal(gin, graph);'
  'if (ch && SPY.nch(k) < 10) || (~ch && SPY.nun(k) < 2)'
  '  if ch, SPY.nch(k) = SPY.nch(k) + 1; else, SPY.nun(k) = SPY.nun(k) + 1; end'
  '  SPY.sg{end + 1} = struct(''graph'', gin, ''cleanstrong'', ps.cleanstrong, ...'
  '    ''rtype'', ps.runps.type, ''fixedall'', ps.fixedall, ...'
  '    ''fixedinternal'', ps.fixedinternal, ''fixedexternal'', ps.fixedexternal, ...'
  '    ''prodtied'', ps.prodtied, ''out'', graph, ''changed'', ch);'
  'end'
  'end'};
spy.subtreeattach = {
  'function graph = subtreeattach(graph, j, edgep, edgec, comp, ps, varargin)'
  'global SPY'
  'gin = graph;'
  'graph = subtreeattach_orig(graph, j, edgep, edgec, comp, ps, varargin{:});'
  'objflag = 0;'
  'for a = 1:2:numel(varargin), if strcmp(varargin{a}, ''objflag''), objflag = varargin{a + 1}; end, end'
  'k = objflag + 1;'
  'if SPY.nst(k) < 6'
  '  SPY.nst(k) = SPY.nst(k) + 1;'
  '  SPY.st{end + 1} = struct(''graph'', gin, ''j'', j, ''edgep'', edgep, ''edgec'', edgec, ...'
  '    ''comp'', comp, ''objflag'', objflag, ''prodtied'', ps.prodtied, ''err'', '''', ...'
  '    ''out'', graph);'
  'end'
  'end'};
for f = fieldnames(spy)'
  fid = fopen(fullfile(spydir, [f{1} '.m']), 'w');
  fprintf(fid, '%s\n', spy.(f{1}){:}); fclose(fid);
end
end
