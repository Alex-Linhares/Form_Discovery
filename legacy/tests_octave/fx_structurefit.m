function fx_structurefit(outfile, seedoffset)
% Fixture for item 27 (L4-c2): structurefit (+ bestsplit, graphscorenoopt,
% optimizebranches, optimizedepth), with every randperm draw recorded through the shim
% (legacy/matlab/octave_shims/randperm.m, pass-through + FD_RANDPERM_LOG) so that Python can
% replay it (formdiscovery.rng.parse_queue).
%
% Re-runs runs with run_baseline.m's settings (speed 54: speed 5, then speed 4; tree runs
% once more after removing the root) while structurefit is replaced by a spy
% (legacy/tests_octave/sf_spy.m; every call is kept) and graph_like by glc_spy.m (item 26),
% which records the slow (ps.fast == 0) calls made inside each structurefit call, and
% choose_node_split by cns_spy.m, which records its calls (to check tied choices). The
% originals are copied to <name>_orig.m in a temporary directory.
%
% ds    the data sets after runmodel's preprocessing (as in fx_gibbs.m). Feature data
%       are stored; Python loads the relational ones.
% runs  structure:data of each run; run_ll its final score (the spy must not change it);
%       run_speed its ps.speed (54 as in run_baseline.m, except a speed-4 chain run that
%       covers the speed 1-4 branch while growing from the empty graph).
% calls one record per structurefit call (see sf_spy.m): kind 'bl' for the calls of the
%       runs, 'cr' for four crafted calls on product graphs with vacant neighbours
%       (craft_calls).
% SEEDOFFSET (default 0) shifts the rand('state') seed of every run (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
sdir = fullfile(root, 'legacy', 'matlab', 'octave_shims');
addpath(mdir);
addpath(here);
addpath(sdir);                 % prepended: the shim shadows the built-in
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd
out = struct();
more off;
tmp = tempname(); mkdir(tmp);
lg = fullfile(tmp, 'log.txt');

dinds = [1 2 3 4];
ds = {};
for k = dinds
  [d, p] = prep(ps0, k, mdir);
  r = struct('name', ps0.data{k}, 'type', p.runps.type);
  if ~strcmp(p.runps.type, 'rel'), r.data = d; end
  ds{end + 1} = r;
end
out.ds = ds;

spydir = tempname(); mkdir(spydir);
rename(mdir, spydir, 'structurefit', 'structurefit(data, ps, graph, savefile)', ...
       'structurefit_orig(data, ps, graph, savefile)', ...
       {'function [ll, graph, bestgraphlls, bestgraph] = structurefit(data, ps, graph, savefile)', ...
        '[ll, graph, bestgraphlls, bestgraph] = sf_spy(data, ps, graph, savefile);'});
rename(mdir, spydir, 'graph_like', 'function [logI graph] = graph_like(', ...
       'function [logI graph] = graph_like_orig(', ...
       {'function [logI, graph] = graph_like(data, graph, ps)', ...
        '[logI, graph] = glc_spy(data, graph, ps);'});
rename(mdir, spydir, 'choose_node_split', '=choose_node_split(graph, compind,', ...
       '=choose_node_split_orig(graph, compind,', ...
       {'function [ll, part1, part2, newgraph] = choose_node_split(graph, compind, splitind, pind, data, ps)', ...
        '[ll, part1, part2, newgraph] = cns_spy(graph, compind, splitind, pind, data, ps);'});
addpath(spydir, '-begin');
global SPY GLREC
GLREC = struct('on', 0, 'list', {{}}, 'cns', {{}});
runs = {{'feat', 2, 1}, {'feat', 4, 2}, {'feat', 6, 3}, {'feat', 8, 2}, {'rel', 17, 4}, ...
        {'feat', 2, 1, 4}};
calls = {};
out.runs = {}; out.run_ll = []; out.run_ncalls = []; out.run_speed = [];
for r = 1:numel(runs)
  SPY = struct('calls', {{}}, 'n', 0, 'log', lg, 'run', r);
  kind = runs{r}{1}; sind = runs{r}{2}; dind = runs{r}{3};
  if numel(runs{r}) > 3, speed = runs{r}{4}; else, speed = 54; end
  randperm_config('', lg);
  out.run_ll(r) = spied_run(mdir, fullfile(tmp, sprintf('r%d', r)), kind, sind, dind, ...
                            1 + seedoffset, speed);
  out.runs{r} = [ps0.structures{sind} ':' ps0.data{dind}];
  out.run_speed(r) = speed;
  out.run_ncalls(r) = SPY.n;
  if isfield(SPY, 'ctx'), ctx = SPY.ctx; ctx.run = r; end
  calls = [calls, SPY.calls];
end
% crafted calls (kind 'cr'): the real runs never try a vacant-neighbour move
% (structurefit.m:46-65, KI-4)
SPY = struct('calls', {{}}, 'n', 0, 'log', lg, 'run', ctx.run, 'kind', 'cr');
calls = [calls, craft_calls(ctx, tmp, 300 + seedoffset)];
randperm_config();
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.calls = calls;
rmpath(sdir);                  % leave a shared (live-test) session with the built-in
clear('randperm', 'graph_like', 'structurefit', 'choose_node_split');

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function calls = craft_calls(ctx, tmp, seedbase)
% Two product graphs, each passed to structurefit at speed 5 and at speed 4 (the run's
% other ps fields), with seeded (logged) draws:
%   1 a 2 x 3 product of the cylinder run's component types (every edge weight set to
%     the mean component weight) with the first half of the objects on node (1, 1) and
%     the rest on (2, 2): both occupied nodes have vacant neighbours (simplified);
%   2 the run's grown graph with its chain dimension extended by a node holding object 1
%     alone and a vacant node.
global SPY
ps = ctx.ps; data = ctx.data; g = ctx.graph; n = g.objcount;
h = floor(n / 2); sz = [2 3]; zz = [ones(1, h), 2 * ones(1, n - h); ones(1, h), 2 * ones(1, n - h)];
for k = 1:2
  m = sz(k); c = g.components{k};
  w = mean(c.W(c.W > 0)); if isnan(w), w = 1; end
  adj = diag(ones(m - 1, 1), 1);
  if strcmp(c.type, 'ring') && m > 2, adj(m, 1) = 1; end
  c.W = w * adj;
  c.adj = adj; c.adjsym = double((adj + adj') > 0); c.Wsym = c.W + c.W';
  c.nodecount = m; c.edgecount = sum(adj(:) > 0); c.edgecountsym = sum(c.adjsym(:) > 0) / 2;
  c.z = zz(k, :); c.illegal = [];
  g.components{k} = c;
end
gs = {simplify_graph(combinegraphs(g, ps), ps)};
% the grown graph with its chain dimension extended by two nodes: object 1 alone on the
% first, the second vacant (a one-object node next to vacant cells, and vacant moves at
% a depth where growth stops)
g = ctx.graph;
kc = find(cellfun(@(c) strcmp(c.type, 'chain'), g.components), 1);
c = g.components{kc}; m = c.nodecount;
w = mean(c.W(c.W > 0)); if isnan(w), w = 1; end
adj = zeros(m + 2); adj(1:m, 1:m) = c.adj; adj(m, m + 1) = 1; adj(m + 1, m + 2) = 1;
W = zeros(m + 2); W(1:m, 1:m) = c.W; W(m, m + 1) = w; W(m + 1, m + 2) = w;
c.adj = adj; c.W = W; c.adjsym = double((adj + adj') > 0); c.Wsym = W + W';
c.nodecount = m + 2; c.edgecount = sum(adj(:) > 0); c.edgecountsym = sum(c.adjsym(:) > 0) / 2;
c.z(1) = m + 1; c.illegal = [];
g.components{kc} = c;
gs{2} = combinegraphs(g, ps);
olddir = pwd; cd(tmp);
for t = 1:4
  p = ps; p.speed = 5 - mod(t + 1, 2);
  rand('state', seedbase + t);
  structurefit(data, p, gs{ceil(t / 2)}, sprintf('crafted%d', t));
end
cd(olddir);
calls = SPY.calls;
end

function [data, ps] = prep(ps, dind, mdir)
% runmodel.m:27-95 without the graph initialisation
names = [];
olddir = pwd; cd(mdir); load(ps.dlocs{dind}); cd(olddir);
[nobjects, ps] = setrunps(data, dind, ps);
[data, ps] = scaledata(data, ps);
end

function rename(mdir, spydir, fname, head, newhead, stub)
% <fname>_orig.m = <fname>.m with its header renamed; <fname>.m = STUB (a forwarder)
src = fileread(fullfile(mdir, [fname '.m']));
orig = strrep(src, head, newhead);
if strcmp(orig, src), error('fx_structurefit: could not rename %s', fname); end
fid = fopen(fullfile(spydir, [fname '_orig.m']), 'w'); fprintf(fid, '%s', orig); fclose(fid);
fid = fopen(fullfile(spydir, [fname '.m']), 'w'); fprintf(fid, '%s\n', stub{:}); fclose(fid);
end

function ll = spied_run(mdir, outdir, kind, sind, dind, seed, speed)
% one run as in legacy/matlab/run_baseline.m (headless ps, rand('state', seed), relational runs
% with reloutsideinit 'overd') at ps.speed SPEED; output goes to OUTDIR
olddir = pwd;
cd(mdir); ps = defaultps(setps());   % setps builds ps.dlocs from pwd
ps.showtruegraph = 0; ps.showinferredgraph = 0; ps.showbestsplit = 0;
ps.showpreclean = 0; ps.showpostclean = 0;
ps.speed = speed;
if strcmp(kind, 'rel'), ps.reloutsideinit = 'overd'; end
if ~exist(outdir, 'dir'), mkdir(outdir); end
cd(outdir);
rand('state', seed);
try
  evalc('ll = runmodel(ps, sind, dind, 1);');
catch err
  cd(olddir); rethrow(err);
end
cd(olddir);
end
