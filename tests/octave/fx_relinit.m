function fx_relinit(outfile, seedoffset)
% Fixture for item 14 (L2-b1): relgraphinit (+chooseinithead, growgraph, finishgraph),
% makelcfreq, filloutrelgraph, reordermissing.
%
% ri_*  relgraphinit(R, z, ps) for every name in ps.structures plus the four domtree names
%       on the 7 relational data sets (ri_dname) and on seeded random relations (ri_R:
%       binary, counts, and an all-zero matrix where every lcprop entry ties), each with
%       z = 1:n (the 'overd' init of runmodel.m:66-75), z = ones (one cluster) and two
%       seeded contiguous partitions (the 'external' init, runmodel.m:54-63). Every record
%       holds the output graph or Octave's error message.
% lc    makelcfreq(R, z) on the data sets (R and R + R') and on non-contiguous labels,
%       where reading lc past length(unique(z)) errors
%       unless no nonzero R entry touches the large label.
% fo    filloutrelgraph on the graph types graph_like_rel.m:8-13 sends to it: the order
%       outputs of ri, seeded split_node sequences for order/ordernoself/connected/
%       connectednoself and the four domtree names, and calls captured by a spy while
%       re-running the baseline runs order, ordernoself, connected, connectednoself x
%       demo_ring_rel_bin and demo_order_rel_freq (run_baseline.m's settings and seed;
%       the first 8 calls that change adjcluster and the first 2 that do not, per run).
%       bl_ll holds each run's final score, which the test compares with the baseline.
% rm    reordermissing on the judges chunks (scaledata, 38 chunks): graphs over judges'
%       13 objects from seeded split_node sequences (rm_graphs), including graphs with
%       unassigned objects (empty_graph + two add_element calls, as in best_split.m:26-32).
%       obsind/missind are built as in dataprobwsig.m:31-34; Wvec is
%       [sigma; leaflengths; random internal weights]; fixedexternal 0 and 1.
% SEEDOFFSET (default 0) shifts the rand('state') seeds (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'matlab', 'formdiscovery1.0');
addpath(mdir);
ps = defaultps(setps());
out = struct();
more off;

names = [ps.structures, {'domtree', 'dirdomtreenoself', 'undirdomtree', 'undirdomtreenoself'}];
out.names = names;
relsets = {'demo_ring_rel_bin', 'demo_hierarchy_rel_bin', 'demo_order_rel_freq', ...
           'mangabeys', 'bushcabinet', 'kularing', 'prisoners'};
Rs = {};
for d = 1:numel(relsets)
  L = load(fullfile(mdir, 'data', [relsets{d} '.mat']));
  Rs{d} = double(L.data.R);
end

% --- relgraphinit ---------------------------------------------------------------------
inputs = {};
for d = 1:numel(relsets), inputs{end + 1} = {relsets{d}, Rs{d}}; end
rand('state', seedoffset + 1);
for n = [5 7 9]
  for rep = 1:2
    inputs{end + 1} = {'', double(rand(n) < 0.3)};
    inputs{end + 1} = {'', floor(rand(n) * 4)};
  end
end
inputs{end + 1} = {'', zeros(6)};
ri = {};
for q = 1:numel(inputs)
  R = inputs{q}{2}; n = size(R, 1);
  zs = {1:n, ones(1, n)};
  for rep = 1:2
    k = 2 + floor(rand() * (n - 2));
    [~, ~, z] = unique(1 + floor(rand(1, n) * k));
    zs{end + 1} = z(:)';
  end
  for t = 1:numel(names)
    p = ps; p.runps.structname = names{t}; p.runps.nobjects = n; p.runps.type = 'rel';
    for zi = 1:numel(zs)
      r = struct('input', q, 'dname', inputs{q}{1}, 'R', [], 'name', names{t}, ...
                 'z', zs{zi}, 'zkind', zi, 'err', '', 'out', 0);
      if isempty(inputs{q}{1}), r.R = R; end
      try
        r.out = relgraphinit(R, zs{zi}, p);
      catch err
        r.err = err.message;
      end
      ri{end + 1} = r;
    end
  end
end
out.ri = ri;

% --- makelcfreq -----------------------------------------------------------------------
lc = {};
rand('state', seedoffset + 2);
for d = 1:numel(relsets)
  R = Rs{d}; n = size(R, 1);
  [~, ~, z] = unique(1 + floor(rand(1, n) * 4)); z = z(:)';
  for zz = {1:n, z}
    for sym = 0:1
      RR = R; if sym, RR = R + R'; end
      lc{end + 1} = struct('dname', relsets{d}, 'R', [], 'z', zz{1}, 'sym', sym, ...
                           'err', '', 'out', makelcfreq(RR, zz{1}));
    end
  end
end
% non-contiguous labels: reading lc(zs(r), zs(c)) past length(unique(z)) errors unless no
% nonzero R entry touches the large label
for rep = 1:4
  R = double(rand(6) < 0.4);
  z = [1 3 3 1 5 2];
  if rep >= 3, R(:, z == 5) = 0; R(z == 5, :) = 0; end
  lc{end + 1} = lcrec(R, z);
end
R = zeros(4); R(2, 1) = 3; R(1, 2) = 1;
lc{end + 1} = lcrec(R, [1 4 2 2]);
lc{end + 1} = lcrec(R, [1 2 4 4]);
out.lc = lc;

% --- filloutrelgraph ------------------------------------------------------------------
fo = {};
filltypes = {'order', 'domtree', 'ordernoself', 'dirdomtreenoself', 'undirdomtree', ...
             'undirdomtreenoself', 'connected', 'connectednoself'};
for q = 1:numel(ri)
  if isempty(ri{q}.err) && any(strcmp(ri{q}.name, filltypes)) && ri{q}.input <= 7
    fo{end + 1} = struct('src', 'ri', 'graph', ri{q}.out, ...
                         'out', filloutrelgraph(ri{q}.out));
  end
end
for s = 1:numel(filltypes)
  p = ps; p.runps.structname = filltypes{s}; p.runps.nobjects = 12; p.runps.type = 'rel';
  g = makeemptygraph(p);
  rand('state', seedoffset + 100 + s);
  for step = 1:8
    comp = g.components{1};
    pind = 1 + floor(rand() * comp.prodcount);
    cands = [];
    for c = 1:comp.nodecount
      if any(comp.z == c), cands(end + 1) = c; end
    end
    c = cands(1 + floor(rand() * numel(cands)));
    members = find(comp.z == c);
    [~, o] = sort(rand(1, numel(members)));
    members = members(o);
    m = max(1, 1 + floor(rand() * (numel(members) - 1)));
    evalc('[g2, c1, c2] = split_node(g, 1, c, pind, members(1:m), members(m + 1:end), p);');
    if isstruct(g2), g = g2; end
    fo{end + 1} = struct('src', 'sq', 'graph', g, 'out', filloutrelgraph(g));
  end
end

% spied baseline runs
spydir = make_spy(mdir);
addpath(spydir, '-begin');
global SPY
runs = {};
for sind = [3 14 15 16]
  for dind = [4 6], runs{end + 1} = {sind, dind}; end
end
tmp = tempname(); mkdir(tmp);
out.bl_run = {}; out.bl_ll = []; out.bl_sind = []; out.bl_dind = [];
for r = 1:numel(runs)
  SPY = struct('fo', {{}}, 'nch', 0, 'nun', 0);
  sind = runs{r}{1}; dind = runs{r}{2};
  out.bl_ll(r) = spied_run(mdir, tmp, sind, dind);
  out.bl_run{r} = [ps.structures{sind} ':' ps.data{dind}];
  out.bl_sind(r) = sind; out.bl_dind(r) = dind;
  for q = 1:numel(SPY.fo), fo{end + 1} = SPY.fo{q}; end
end
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.fo = fo;

% --- reordermissing -------------------------------------------------------------------
L = load(fullfile(mdir, 'data', 'judges.mat'));
[~, pj] = setrunps(L.data, 13, ps);
[~, pj] = scaledata(L.data, pj);
out.rm_chunknum = pj.runps.chunknum;
nobj = size(L.data, 1);
rmnames = {'chain', 'ring', 'tree', 'hierarchy', 'partition', 'connected', 'grid', 'cylinder'};
graphs = {};
for s = 1:numel(rmnames)
  p = ps; p.runps.structname = rmnames{s}; p.runps.nobjects = nobj; p.runps.type = 'feat';
  g = makeemptygraph(p);
  rand('state', seedoffset + 200 + s);
  for step = 1:5
    for j = 1:g.ncomp
      g.components{j}.W = g.components{j}.adj .* (0.5 + rand(size(g.components{j}.adj)));
    end
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
    m = max(1, 1 + floor(rand() * (numel(members) - 1)));
    part1 = members(1:m); part2 = members(m + 1:end);
    evalc('[g2, c1, c2] = split_node(g, i, c, pind, part1, part2, p);');
    if ~isstruct(g2), continue; end
    g = g2;
    if step >= 3 && ~isempty(part2) && numel(members) >= 3
      % best_split.m:26-32: empty the two new nodes, re-add one seed each
      e = empty_graph(g, i, c1, c2);
      e = add_element(e, i, c1, part1(1), p);
      e = add_element(e, i, c2, part2(1), p);
      e.leaflengths = 0.5 + rand(1, numel(e.z));
      graphs{end + 1} = e;
    end
  end
  g.leaflengths = 0.5 + rand(1, numel(g.z));
  graphs{end + 1} = g;
end
rm = {};
for gi = 1:numel(graphs)
  g = graphs{gi};
  theseobjs = g.z >= 0;
  Wvec = [g.sigma; g.leaflengths(theseobjs)'; 0.5 + rand(4, 1)];
  for c = 1:pj.runps.chunknum
    obsind = find(theseobjs & sparse(1, pj.runps.objind{c}, 1, 1, length(g.z)));
    missind = find(theseobjs & ~sparse(1, pj.runps.objind{c}, 1, 1, length(g.z)));
    for fe = 0:1
      p = ps; p.fixedexternal = fe;
      [ng, nW] = reordermissing(g, Wvec, obsind, missind, p);
      rm{end + 1} = struct('graph', gi, 'chunk', c, 'obsind', obsind, 'missind', missind, ...
                           'fixedexternal', fe, 'Wvec', Wvec, 'out', ng, 'Wout', nW);
    end
  end
end
out.rm_graphs = graphs;
out.rm = rm;

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function r = lcrec(R, z)
r = struct('dname', '', 'R', R, 'z', z, 'sym', 0, 'err', '', 'out', 0);
try
  r.out = makelcfreq(R, z);
catch err
  r.err = err.message;
end
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

function spydir = make_spy(mdir)
% filloutrelgraph_orig.m = filloutrelgraph.m renamed; filloutrelgraph.m = a logging spy
spydir = tempname(); mkdir(spydir);
src = fileread(fullfile(mdir, 'filloutrelgraph.m'));
src = regexprep(src, '=\s*filloutrelgraph\(', '= filloutrelgraph_orig(', 'once');
fid = fopen(fullfile(spydir, 'filloutrelgraph_orig.m'), 'w'); fprintf(fid, '%s', src); fclose(fid);
spy = {
  'function graph = filloutrelgraph(graph)'
  'global SPY'
  'gin = graph;'
  'graph = filloutrelgraph_orig(graph);'
  'ch = ~isequal(double(gin.adjcluster), double(graph.adjcluster));'
  'if (ch && SPY.nch < 8) || (~ch && SPY.nun < 2)'
  '  if ch, SPY.nch = SPY.nch + 1; else, SPY.nun = SPY.nun + 1; end'
  '  SPY.fo{end + 1} = struct(''src'', ''bl'', ''graph'', gin, ''out'', graph);'
  'end'
  'end'};
fid = fopen(fullfile(spydir, 'filloutrelgraph.m'), 'w');
fprintf(fid, '%s\n', spy{:}); fclose(fid);
end
