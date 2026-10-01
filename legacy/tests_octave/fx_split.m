function fx_split(outfile, seedoffset)
% Fixture for item 12 (L2-a2): split_node, empty_graph, add_element.
%
% sq_*  seeded split sequences: from makeemptygraph (12 objects) for the 26 single-component
%       names and grid/cylinder (these with prodtied 0 and 1), 8 steps each. Each step
%       gives every component W (and the graph Wcluster) seeded random weights, so the
%       weight bookkeeping of split_node (markers, median, origgraph copy) moves distinct
%       values; picks a component, a production pind in 1..prodcount, a node holding
%       objects and a random partition of its members, and calls split_node. When the
%       production applies, it then calls empty_graph(g2, i, c1, c2) and two add_element
%       calls on the emptied graph (as best_split.m:26-32 does), and the high-level
%       variants empty_graph(g, -1, ...) / add_element(e, -1, ...) on the combined graph.
%       Records: sp (split_node calls), eg (empty_graph), ae (add_element).
% bl_*  split_node / empty_graph / add_element calls captured by spies while re-running
%       baseline runs (runmodel with run_baseline.m's settings and seed; run_baseline
%       itself cannot be used because its addpath puts the sources ahead of the spies): chain/ring/tree x demo_chain_feat and
%       the 18 relational structures x demo_ring_rel_bin. Per run the first 3 calls of each
%       pind, the first 2 that return -inf, the first 3 empty_graph and the first 8
%       add_element calls are kept. bl_ll holds each run's final score, which the test
%       compares with the committed baseline (the spies must not change the run).
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

% --- seeded sequences -----------------------------------------------------------------
names = [ps.structures, {'domtree', 'dirdomtreenoself', 'undirdomtree', 'undirdomtreenoself'}];
names = names(~strcmp(names, 'grid') & ~strcmp(names, 'cylinder'));
starts = {};
for t = 1:numel(names), starts{end + 1} = {names{t}, 0}; end
for t = {'grid', 'cylinder'}
  for pt = 0:1, starts{end + 1} = {t{1}, pt}; end
end
sp = {}; eg = {}; ae = {};
out.sq_name = {};
for s = 1:numel(starts)
  name = starts{s}{1}; pt = starts{s}{2};
  out.sq_name{s} = sprintf('%s:prodtied%d', name, pt);
  p = ps; p.prodtied = pt; p.runps.structname = name; p.runps.nobjects = 12;
  p.runps.type = 'feat';
  g = makeemptygraph(p);
  rand('state', seedoffset + s);
  for step = 1:8
    for j = 1:g.ncomp
      g.components{j}.W = g.components{j}.adj .* (0.5 + rand(size(g.components{j}.adj)));
    end
    g.Wcluster = g.adjcluster .* (0.5 + rand(size(g.adjcluster)));
    i = 1 + (g.ncomp > 1) * (rand() > 0.5);
    comp = g.components{i};
    pind = 1 + floor(rand() * comp.prodcount);
    cands = [];
    for c = 1:comp.nodecount
      if any(comp.z == c), cands(end + 1) = c; end
    end
    c = cands(1 + floor(rand() * numel(cands)));
    members = find(comp.z == c);
    [~, o] = sort(rand(1, numel(members)));
    members = members(o);
    if numel(members) >= 2
      m = 1 + floor(rand() * (numel(members) - 1));
    else
      m = 1;
    end
    part1 = members(1:m); part2 = members(m + 1:end);
    [g2, c1, c2] = quiet_split(g, i, c, pind, part1, part2, p);
    sp{end + 1} = struct('seq', s, 'step', step, 'graph', g, 'compind', i, 'c', c, ...
                         'pind', pind, 'part1', part1, 'part2', part2, 'prodtied', pt, ...
                         'out', g2, 'c1', c1, 'c2', c2, 'isinf', ~isstruct(g2));
    if ~isstruct(g2), continue; end
    e = empty_graph(g2, i, c1, c2);
    eg{end + 1} = struct('seq', s, 'graph', g2, 'compind', i, 'c1', c1, 'c2', c2, 'out', e);
    a1 = add_element(e, i, c1, part1(1), p);
    ae{end + 1} = struct('seq', s, 'graph', e, 'compind', i, 'c', c1, 'element', part1(1), ...
                         'prodtied', pt, 'out', a1);
    if isempty(part2), el = part1(end); else, el = part2(1); end
    a2 = add_element(a1, i, c2, el, p);
    ae{end + 1} = struct('seq', s, 'graph', a1, 'compind', i, 'c', c2, 'element', el, ...
                         'prodtied', pt, 'out', a2);
    g = g2;
    % high-level variants on the combined graph (compind = -1, best_split.m:12-15)
    nclus = size(g.adjcluster, 1);
    occ = unique(g.z(g.z > 0));
    ch = occ(1 + floor(rand() * numel(occ)));
    other = 1 + floor(rand() * nclus);
    e = empty_graph(g, -1, ch, other);
    eg{end + 1} = struct('seq', s, 'graph', g, 'compind', -1, 'c1', ch, 'c2', other, 'out', e);
    el = find(g.z == ch, 1);
    a = add_element(e, -1, ch, el, p);
    ae{end + 1} = struct('seq', s, 'graph', e, 'compind', -1, 'c', ch, 'element', el, ...
                         'prodtied', pt, 'out', a);
  end
end
out.sq_sp = sp; out.sq_eg = eg; out.sq_ae = ae;

% --- spied baseline runs --------------------------------------------------------------
spydir = make_spies(mdir);
addpath(spydir, '-begin');
global SPY
runs = {};
for sind = [2 4 6], runs{end + 1} = {'feat', sind, 1}; end
for sind = [1, 9, 10:13, 3, 14:24], runs{end + 1} = {'rel', sind, 4}; end
tmp = tempname(); mkdir(tmp);
bl_sp = {}; bl_eg = {}; bl_ae = {};
out.bl_run = {}; out.bl_ll = [];
for r = 1:numel(runs)
  SPY = struct('sp', {{}}, 'eg', {{}}, 'ae', {{}}, 'npind', [0 0 0], 'ninf', 0);
  kind = runs{r}{1}; sind = runs{r}{2}; dind = runs{r}{3};
  out.bl_ll(r) = spied_run(mdir, fullfile(tmp, kind), kind, sind, dind);
  out.bl_run{r} = [ps.structures{sind} ':' ps.data{dind}];
  for q = 1:numel(SPY.sp), SPY.sp{q}.run = r; bl_sp{end + 1} = SPY.sp{q}; end
  for q = 1:numel(SPY.eg), SPY.eg{q}.run = r; bl_eg{end + 1} = SPY.eg{q}; end
  for q = 1:numel(SPY.ae), SPY.ae{q}.run = r; bl_ae{end + 1} = SPY.ae{q}; end
end
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.bl_sp = bl_sp; out.bl_eg = bl_eg; out.bl_ae = bl_ae;

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
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
for f = {'split_node', 'empty_graph', 'add_element'}
  src = fileread(fullfile(mdir, [f{1} '.m']));
  src = regexprep(src, ['=\s*' f{1} '\('], ['= ' f{1} '_orig('], 'once');
  fid = fopen(fullfile(spydir, [f{1} '_orig.m']), 'w'); fprintf(fid, '%s', src); fclose(fid);
end
spy.split_node = {
  'function [graph, c1, c2] = split_node(graph, compind, c, pind, part1, part2, ps)'
  'global SPY'
  'gin = graph;'
  '[graph, c1, c2] = split_node_orig(graph, compind, c, pind, part1, part2, ps);'
  'isinf_ = ~isstruct(graph);'
  'if (isinf_ && SPY.ninf < 2) || (~isinf_ && SPY.npind(pind) < 3)'
  '  if isinf_, SPY.ninf = SPY.ninf + 1; else, SPY.npind(pind) = SPY.npind(pind) + 1; end'
  '  SPY.sp{end + 1} = struct(''graph'', gin, ''compind'', compind, ''c'', c, ''pind'', pind, ...'
  '    ''part1'', part1, ''part2'', part2, ''prodtied'', ps.prodtied, ''out'', graph, ...'
  '    ''c1'', c1, ''c2'', c2, ''isinf'', isinf_);'
  'end'
  'end'};
spy.empty_graph = {
  'function graph = empty_graph(graph, compind, c1, c2)'
  'global SPY'
  'gin = graph;'
  'graph = empty_graph_orig(graph, compind, c1, c2);'
  'if numel(SPY.eg) < 3'
  '  SPY.eg{end + 1} = struct(''graph'', gin, ''compind'', compind, ''c1'', c1, ''c2'', c2, ...'
  '    ''out'', graph);'
  'end'
  'end'};
spy.add_element = {
  'function g = add_element(g, compind, c, element, ps)'
  'global SPY'
  'gin = g;'
  'g = add_element_orig(g, compind, c, element, ps);'
  'if numel(SPY.ae) < 8'
  '  SPY.ae{end + 1} = struct(''graph'', gin, ''compind'', compind, ''c'', c, ...'
  '    ''element'', element, ''prodtied'', ps.prodtied, ''out'', g);'
  'end'
  'end'};
for f = fieldnames(spy)'
  fid = fopen(fullfile(spydir, [f{1} '.m']), 'w');
  fprintf(fid, '%s\n', spy.(f{1}){:}); fclose(fid);
end
end
