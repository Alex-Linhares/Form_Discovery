function fx_swap(outfile, seedoffset)
% Fixture for item 24 (L4-b1): swapobjclust and its subfunctions chooseswaps, doswap,
% sourceobjs, sourcecls and cltypes, with every randperm draw recorded through the shim
% (matlab/octave_shims/randperm.m, pass-through + FD_RANDPERM_LOG) so that Python can
% replay it (formdiscovery.rng.parse_queue).
%
% The calls come from re-running baseline runs with run_baseline.m's settings while
% swapobjclust is replaced by a spy (tests/octave/swap_spy.m; its header describes what
% is kept). The subfunctions are reached through swsub.m, a copy of swapobjclust.m's
% subfunctions behind a dispatcher. Both live in a temporary directory.
%
% ds    the data sets after runmodel's preprocessing (as in fx_search.m). Feature data
%       are stored; Python loads the relational ones.
% runs  structure:data of each run; run_ll its final score, which the test compares with
%       the committed baseline where there is one (the spy must not change the run).
% sw    kept calls: 'bl' (the real call) and 'pt' (same mode on a perturbed graph).
%       Inputs, the ps fields that vary, the draws (logtext) and every output; near-miss
%       graphs that were in the input list appear as the strings 'in1', 'in2', ...
% sub   subfunction outputs on the input graph of the first kept call per mode and run.
%
% The runs cover chain, ring, tree, hierarchy, grid and cylinder on the feature demos and
% dirring, undirchain, order, dirhierarchy and undirhierarchy on the relational demos:
% object moves, within-component cluster moves and swaps, whole-graph moves and swaps
% (grid, cylinder), fast (dijkstra neighbourhood) and full modes, with and without
% near-miss lists, and the sourceobjs/sourcecls type lists.
% SEEDOFFSET (default 0) shifts the rand('state') seed of every run (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'matlab', 'formdiscovery1.0');
sdir = fullfile(root, 'matlab', 'octave_shims');
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
ds = {};
for k = 1:6
  [d, p] = prep(ps0, k, mdir);
  r = struct('name', ps0.data{k}, 'type', p.runps.type);
  if ~strcmp(p.runps.type, 'rel'), r.data = d; end
  ds{end + 1} = r;
end
out.ds = ds;

% --- spied runs -------------------------------------------------------------------------
spydir = make_spy(mdir);
addpath(spydir, '-begin');
global SPY
runs = {{'feat', 2, 1}, {'feat', 4, 2}, {'feat', 6, 3}, {'feat', 5, 3}, ...
        {'feat', 7, 1}, {'feat', 8, 2}, ...
        {'rel', 17, 4}, {'rel', 12, 6}, {'rel', 3, 6}, {'rel', 21, 5}, {'rel', 23, 5}};
calls = {}; subs = {};
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
end
randperm_config();
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.sw = calls;
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

function spydir = make_spy(mdir)
% swapobjclust_orig.m = swapobjclust.m renamed; swapobjclust.m forwards to swap_spy.m;
% swsub.m = the subfunctions of swapobjclust.m behind a dispatcher
spydir = tempname(); mkdir(spydir);
src = fileread(fullfile(mdir, 'swapobjclust.m'));
orig = regexprep(src, '(\s)swapobjclust\(graph, data', '$1swapobjclust_orig(graph, data', 'once');
if strcmp(orig, src), error('fx_swap: could not rename swapobjclust'); end
fid = fopen(fullfile(spydir, 'swapobjclust_orig.m'), 'w');
fprintf(fid, '%s', orig); fclose(fid);
fid = fopen(fullfile(spydir, 'swapobjclust.m'), 'w');
fprintf(fid, '%s\n', ...
  'function [graph, currscore, overallchange, nearmscores, nearmgraphs] = swapobjclust(varargin)', ...
  '[graph, currscore, overallchange, nearmscores, nearmgraphs] = swap_spy(varargin{:});');
fclose(fid);
k = strfind(src, 'function [sw1 sw2]= chooseswaps');
if isempty(k), error('fx_swap: chooseswaps not found'); end
lines = {
  'function varargout = swsub(name, varargin)'
  'switch name'
  '  case ''chooseswaps'', [varargout{1}, varargout{2}] = chooseswaps(varargin{:});'
  '  case ''doswap'', varargout{1} = doswap(varargin{:});'
  '  case ''sourceobjs'', varargout{1} = sourceobjs(varargin{:});'
  '  case ''sourcecls'', varargout{1} = sourcecls(varargin{:});'
  '  case ''cltypes'', [varargout{1}, varargout{2}] = cltypes(varargin{:});'
  '  otherwise, error(''swsub: unknown %s'', name);'
  'end'
  ''};
fid = fopen(fullfile(spydir, 'swsub.m'), 'w');
fprintf(fid, '%s\n', lines{:});
fprintf(fid, '%s', src(k(1):end)); fclose(fid);
end

function ll = spied_run(mdir, outdir, kind, sind, dind, seed)
% one run as in matlab/run_baseline.m (headless ps, rand('state', seed), relational runs
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
