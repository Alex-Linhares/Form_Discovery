function fx_spr(outfile, seedoffset)
% Fixture for item 25 (L4-b2): spr (+ makerp, makers) and collapsedims (+ getocc,
% get_occnodescomp, zassign), with every randperm draw recorded through the shim
% (legacy/matlab/octave_shims/randperm.m, pass-through + FD_RANDPERM_LOG) so that Python can
% replay it (formdiscovery.rng.parse_queue).
%
% The calls come from re-running runs with run_baseline.m's settings while spr and
% collapsedims are replaced by a spy (legacy/tests_octave/l4b2_spy.m; its header describes what
% is kept). The originals are copied to spr_orig.m / collapsedims_orig.m and their
% subfunctions to sprsub.m / cdsub.m behind dispatchers; swsub.m (swapobjclust.m's
% subfunctions) is used to perturb graphs. All live in a temporary directory.
%
% ds    the data sets after runmodel's preprocessing (as in fx_swap.m). Feature data
%       are stored; Python loads the relational ones.
% runs  structure:data of each run; run_ll its final score (the spy must not change it).
% calls kept calls: fn 'spr' or 'collapsedims', kind 'bl' (the real call) or 'pt' (a
%       perturbed graph). Inputs, the ps fields that vary, the draws (logtext) and every
%       output; near-miss graphs that were in the input list appear as 'in1', 'in2', ...
% sub   subfunction outputs on the input graph of the first kept call per mode and run.
%
% spr: tree and hierarchy on demo_tree_feat, tree on demo_chain_feat, and the four
% relational hierarchies on demo_hierarchy_rel_bin (cluster and object pruning, tree
% edges and hierarchy nodes). collapsedims: grid and cylinder runs on the feature demos
% and on synthgrid (product graphs with two dimensions of size > 1).
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

% --- ds: data sets ----------------------------------------------------------------------
dinds = [1 2 3 5 11];
ds = {};
for k = dinds
  [d, p] = prep(ps0, k, mdir);
  r = struct('name', ps0.data{k}, 'type', p.runps.type);
  if ~strcmp(p.runps.type, 'rel'), r.data = d; end
  ds{end + 1} = r;
end
out.ds = ds;

% --- spied runs -------------------------------------------------------------------------
spydir = tempname(); mkdir(spydir);
make_spy(mdir, spydir, 'spr', 'function rp = makerp', {'makerp', 1; 'makers', 2});
make_spy(mdir, spydir, 'collapsedims', 'function [occ unocc] = getocc', ...
         {'getocc', 2; 'get_occnodescomp', 1; 'zassign', 1});
make_spy(mdir, spydir, 'swapobjclust', 'function [sw1 sw2]= chooseswaps', ...
         {'chooseswaps', 2; 'doswap', 1}, 'swsub');
addpath(spydir, '-begin');
global SPY
runs = {{'feat', 6, 3}, {'feat', 5, 3}, {'feat', 6, 1}, ...
        {'rel', 21, 5}, {'rel', 22, 5}, {'rel', 23, 5}, {'rel', 24, 5}, ...
        {'feat', 8, 2}, {'feat', 7, 2}, {'feat', 8, 1}, {'feat', 7, 11}};
calls = {}; subs = {}; ctxs = {};
out.runs = {}; out.run_ll = []; out.run_ncalls = [];
for r = 1:numel(runs)
  SPY = struct('calls', {{}}, 'subs', {{}}, 'n', 0, 'log', lg, 'run', r, ...
               'kept', struct(), 'keptch', struct(), 'subdone', struct());
  kind = runs{r}{1}; sind = runs{r}{2}; dind = runs{r}{3};
  randperm_config('', lg);
  out.run_ll(r) = spied_run(mdir, fullfile(tmp, kind), kind, sind, dind, 1 + seedoffset);
  out.runs{r} = [ps0.structures{sind} ':' ps0.data{dind}];
  out.run_ncalls(r) = SPY.n;
  calls = [calls, SPY.calls];
  subs = [subs, SPY.subs];
  if isfield(SPY, 'ctx'), ctxs{end + 1} = SPY.ctx; end
end
% crafted collapsedims calls (kind 'cr') on the contexts of the grid/cylinder runs
for c = 1:numel(ctxs)
  calls = [calls, craft_calls(ctxs{c}, lg, 100 * c + seedoffset)];
end
randperm_config();
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.calls = calls;
out.sub = subs;
rmpath(sdir);                  % leave a shared (live-test) session with the built-in
clear('randperm');

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function [data, ps] = prep(ps, dind, mdir)
% runmodel.m:27-95 without the graph initialisation
names = [];
olddir = pwd; cd(mdir); load(ps.dlocs{dind}); cd(olddir);
[nobjects, ps] = setrunps(data, dind, ps);
[data, ps] = scaledata(data, ps);
end

function calls = craft_calls(ctx, lg, seedbase)
% Product graphs where collapsing a dimension can pay off. The run's last kept input graph
% to collapsedims gives sigma, leaf lengths and the component types; its components are
% replaced by a 2 x n or 3 x m chain/ring product with every edge weight set to the mean
% component weight (cases 1, 3) or to that mean times a random factor in [0.5, 1.5)
% (cases 2, 4, so that dijkstra distances are not ties):
%   1 zigzag  object k at (mod(k-1, 2) + 1, k)
%   2 zigzag  in a random object order
%   3 block   the first half of the objects in row 1, columns 1..h; the rest in row 2,
%             columns h+1..n
%   4 random  3 x (ceil(n/2) + 1), objects on distinct random nodes
% Each is simplified, scored and passed to collapsedims with loopmax 1-3 and a near-miss
% list of length 0 or 5, with seeded (logged) draws.
calls = {};
ps = ctx.ps; data = ctx.data; g0 = ctx.graph; n = g0.objcount;
for t = 1:4
  rand('state', seedbase + t);
  switch t
    case 1, sz = [2 n]; zz = [mod(0:n-1, 2) + 1; 1:n];
    case 2, sz = [2 n]; p = builtin('randperm', n); zz = [mod(0:n-1, 2) + 1; 1:n]; zz = zz(:, p);
    case 3, h = floor(n / 2); sz = [2 n]; zz = [ones(1, h), 2 * ones(1, n - h); 1:n];
    case 4
      sz = [3, ceil(n / 2) + 1]; p = builtin('randperm', prod(sz), n);
      [a1, a2] = ind2sub(sz, p); zz = [a1; a2];
  end
  g = g0;
  for k = 1:2
    m = sz(k); c = g.components{k};
    w = mean(c.W(c.W > 0)); if isnan(w), w = 1; end
    adj = diag(ones(m - 1, 1), 1);
    if strcmp(c.type, 'ring') && m > 2, adj(m, 1) = 1; end
    if mod(t, 2), c.W = w * adj; else, c.W = w * adj .* (0.5 + rand(m)); end
    c.adj = adj; c.adjsym = double((adj + adj') > 0); c.Wsym = c.W + c.W';
    c.nodecount = m; c.edgecount = sum(adj(:) > 0); c.edgecountsym = sum(c.adjsym(:) > 0) / 2;
    c.z = zz(k, :); c.illegal = [];
    g.components{k} = c;
  end
  g = simplify_graph(combinegraphs(g, ps), ps);
  [tl, tng] = graph_like(data, g, ps);
  tscore = tl + graph_prior(g, ps);
  if mod(t, 2), nm = -inf * ones(1, 5); else, nm = []; end
  ph = arrayfun(@(k) sprintf('in%d', k), 1:numel(nm), 'UniformOutput', false);
  lm = 1 + mod(t + seedbase, 3);
  fid = fopen(lg, 'w'); fclose(fid);
  rand('state', seedbase + 50 + t);
  [g4, cs4, oc4, ns4, ng4] = collapsedims_orig(g, data, ps, 1e-4, tscore, 0, lm, nm, ph);
  r = struct('fn', 'collapsedims', 'run', ctx.run, 'n', t, 'kind', 'cr', 'graph', g, ...
    'comp', 0, 'epsilon', 1e-4, 'currscore', tscore, 'overallchange', 0, 'loopmax', lm, ...
    'nearmscores', nm, 'ps', ctx.q, 'logtext', fileread(lg), 'out_graph', g4, ...
    'out_currscore', cs4, 'out_overallchange', oc4, 'out_nearmscores', ns4);
  r.out_nearmgraphs = ng4;
  calls{end + 1} = r;
end
end

function make_spy(mdir, spydir, fname, subhead, subs, subfile)
% <fname>_orig.m = <fname>.m renamed; <fname>.m forwards to l4b2_spy.m (unless SUBFILE is
% given: then only the dispatcher is written); <subfile>.m (default <prefix>sub.m) = the
% subfunctions of <fname>.m (from SUBHEAD on) behind a dispatcher. SUBS lists
% {name, nargout}.
src = fileread(fullfile(mdir, [fname '.m']));
if nargin < 6
  orig = regexprep(src, ['(\s)' fname '\(graph, data'], ['$1' fname '_orig(graph, data'], 'once');
  if strcmp(orig, src), error('fx_spr: could not rename %s', fname); end
  fid = fopen(fullfile(spydir, [fname '_orig.m']), 'w');
  fprintf(fid, '%s', orig); fclose(fid);
  fid = fopen(fullfile(spydir, [fname '.m']), 'w');
  fprintf(fid, '%s\n', ...
    ['function [graph, currscore, overallchange, nearmscores, nearmgraphs] = ' fname '(varargin)'], ...
    ['[graph, currscore, overallchange, nearmscores, nearmgraphs] = l4b2_spy(''' fname ''', varargin{:});']);
  fclose(fid);
  if strcmp(fname, 'spr'), subfile = 'sprsub'; else, subfile = 'cdsub'; end
end
k = strfind(src, subhead);
if isempty(k), error('fx_spr: %s not found', subhead); end
lines = {sprintf('function varargout = %s(name, varargin)', subfile), 'switch name'};
for s = 1:size(subs, 1)
  outs = strjoin(arrayfun(@(m) sprintf('varargout{%d}', m), 1:subs{s, 2}, ...
                          'UniformOutput', false), ', ');
  lines{end + 1} = sprintf('  case ''%s'', [%s] = %s(varargin{:});', subs{s, 1}, outs, subs{s, 1});
end
lines{end + 1} = sprintf('  otherwise, error(''%s: unknown %%s'', name);', subfile);
lines{end + 1} = 'end';
lines{end + 1} = '';
fid = fopen(fullfile(spydir, [subfile '.m']), 'w');
fprintf(fid, '%s\n', lines{:});
fprintf(fid, '%s', src(k(1):end)); fclose(fid);
end

function ll = spied_run(mdir, outdir, kind, sind, dind, seed)
% one run as in legacy/matlab/run_baseline.m (headless ps, rand('state', seed), relational runs
% with reloutsideinit 'overd'); output goes to OUTDIR
olddir = pwd;
cd(mdir); ps = defaultps(setps());   % setps builds ps.dlocs from pwd
ps.showtruegraph = 0; ps.showinferredgraph = 0; ps.showbestsplit = 0;
ps.showpreclean = 0; ps.showpostclean = 0;
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
