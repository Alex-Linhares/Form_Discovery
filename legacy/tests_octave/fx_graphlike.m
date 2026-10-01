function fx_graphlike(outfile, seedoffset)
% Fixture for item 18 (L3-b1): graph_like (dispatcher) and graph_like_conn in fast mode
% (ps.fast = 1).
%
% ds    the three demo feature sets after runmodel's preprocessing (setrunps, scaledata,
%       structcounts; runmodel.m:30-95): name, data, and the runps fields that
%       dataprobwsig reads.
% gh    every bestgraph of the 19 feature baseline growth histories, scored by
%       [logI g] = graph_like(data, graph, ps) with ps.fast = 1 in the tying mode the file
%       was grown in (alltie: fixedinternal = fixedexternal = 1; exttie: fixedexternal = 1;
%       notie/noinit: none) and, for tied files, also untied. Each record stores logI, the
%       returned graph, graph_prior and the file's bestgraphlls entry.
% sy    graphs over 10 objects from tests/fixtures/dataprob.mat (gr, including graphs with
%       unassigned objects, z = -1) with random 10 x 20 feature data and 10 x 10
%       similarity data (runps.dim = 30), in tying modes none, fixedexternal, fixedall and
%       prodtied, so graph_like's data(currobj,:) / data(currobj,currobj) subsetting runs.
%       Errors are recorded.
% jd    graphs over judges' 13 objects from tests/fixtures/dpmiss.mat (gr) with the judges
%       ps (ps.missingdata = 1, the chunk path), modes none and fixedexternal.
% bl    graph_like calls captured by a spy while re-running chain x demo_chain_feat and
%       tree x demo_tree_feat with run_baseline.m's settings and seed: every 37th
%       fast-mode call (at most 15 per run) with its inputs (ps fields) and outputs.
%       bl_ll holds each run's final score (compared with the committed baseline),
%       bl_nfast / bl_nslow the number of fast / slow calls.
% SEEDOFFSET (default 0) shifts the rand/randn('state') seeds of sy and jd (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
fxdir = fullfile(root, 'tests', 'fixtures');
addpath(mdir);
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd
out = struct();
more off;

MODES = [0 0 0 0; 0 0 1 0; 0 1 0 0; 0 1 1 0; 1 0 0 0; 0 0 0 1; 0 0 1 1; 0 1 0 1];
out.modes = MODES;

% --- demo feature data sets -----------------------------------------------------------
dps = {};
ds = {};
for dind = 1:3
  [data, p] = prep(ps0, dind);
  dps{dind} = p;
  ds{dind} = struct('name', ps0.data{dind}, 'data', data, 'chunkcount', p.runps.chunkcount, ...
                    'SS', p.runps.SS, 'type', p.runps.type);
end
out.ds = ds;

% --- baseline growth histories --------------------------------------------------------
d = fullfile(fxdir, 'baseline', 'feat', 'results');
files = {};
st = dir(d);
for a = 1:numel(st)
  if st(a).name(1) == '.', continue; end
  sd = dir(fullfile(d, st(a).name));
  for b = 1:numel(sd)
    if sd(b).name(1) == '.', continue; end
    fs = dir(fullfile(d, st(a).name, sd(b).name, 'growthhistory*.mat'));
    for c = 1:numel(fs)
      files{end + 1} = {fullfile(d, st(a).name, sd(b).name, fs(c).name), ...
                        [st(a).name '/' sd(b).name '/' fs(c).name], sd(b).name, fs(c).name};
    end
  end
end
gh = {};
out.gh_file = {};
for f = 1:numel(files)
  out.gh_file{f} = files{f}{2};
  dind = find(strcmp(ps0.data, files{f}{3}(1:end - 1)));
  fname = files{f}{4};
  if ~isempty(strfind(fname, 'alltie')), m = 4;
  elseif ~isempty(strfind(fname, 'exttie')), m = 2;
  else m = 1; end
  L = load(files{f}{1});
  for k = 1:numel(L.bestgraph)
    g = L.bestgraph{k};
    if ~isstruct(g), continue; end
    for mi = unique([m 1])
      p = setmode(dps{dind}, MODES(mi, :));
      p.runps.structname = g.type; p.fast = 1;
      r = struct('file', f, 'depth', k, 'data', dind, 'mode', mi, 'filemode', m, ...
                 'graph', g, 'bgll', L.bestgraphlls(k), 'err', '', 'logI', [], ...
                 'out', [], 'prior', []);
      try
        [r.logI, r.out] = graph_like(ds{dind}.data, g, p);
        r.prior = graph_prior(r.out, p);
      catch err
        r.err = err.message;
      end
      gh{end + 1} = r;
    end
  end
end
out.gh = gh;

% --- synthetic graphs with unassigned objects -----------------------------------------
F = load(fullfile(fxdir, 'dataprob.mat'));
sy = {};
randn('state', seedoffset + 900); rand('state', seedoffset + 901);
nobj = 10; nfeat = 20; simdim = 30;
for q = 1:numel(F.gr)
  g = F.gr{q}.graph;
  A = randn(nobj, simdim);
  dats = {randn(nobj, nfeat), A * A' / simdim};
  for v = 1:2
    for mi = [1 2 5 6]
      p = setmode(ps0, MODES(mi, :));
      p.missingdata = 0; p.overrideSS = 0; p.zglreg = 0; p.fast = 1;
      p.runps.chunkcount = -1; p.runps.SS = [];
      if v == 1, p.runps.type = 'feat'; else p.runps.type = 'sim'; p.runps.dim = simdim; end
      r = struct('src', F.gr{q}.src, 'graph', g, 'variant', v, 'mode', mi, ...
                 'd', dats{v}, 'err', '', 'logI', [], 'out', []);
      try
        [r.logI, r.out] = graph_like(dats{v}, g, p);
      catch err
        r.err = err.message;
      end
      sy{end + 1} = r;
    end
  end
end
out.sy = sy;

% --- judges (missing-data chunk path) -------------------------------------------------
jind = find(strcmp(ps0.data, 'judges'));
[jdata, pj] = prep(ps0, jind);
out.jdata = jdata;
D = load(fullfile(fxdir, 'dpmiss.mat'));
jd = {};
for q = 1:numel(D.gr)
  g = D.gr{q}.graph;
  for mi = [1 2]
    p = setmode(pj, MODES(mi, :));
    p.runps.structname = g.type; p.fast = 1;
    r = struct('src', D.gr{q}.src, 'graph', g, 'mode', mi, 'err', '', 'logI', [], 'out', []);
    try
      [r.logI, r.out] = graph_like(jdata, g, p);
    catch err
      r.err = err.message;
    end
    jd{end + 1} = r;
  end
end
out.jd = jd;

% --- spied baseline runs --------------------------------------------------------------
spydir = make_spy(mdir);
addpath(spydir, '-begin');
global SPY
tmp = tempname(); mkdir(tmp);
bl = {};
out.bl_run = {}; out.bl_ll = []; out.bl_nfast = []; out.bl_nslow = [];
runs = {{'chain', 1}, {'tree', 3}};
for r = 1:numel(runs)
  SPY = struct('calls', {{}}, 'nfast', 0, 'nslow', 0);
  sind = find(strcmp(ps0.structures, runs{r}{1}));
  out.bl_ll(r) = spied_run(mdir, tmp, sind, runs{r}{2});
  out.bl_run{r} = [runs{r}{1} ':' ps0.data{runs{r}{2}}];
  out.bl_nfast(r) = SPY.nfast; out.bl_nslow(r) = SPY.nslow;
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

function [data, ps] = prep(ps, dind)
% runmodel.m:27-95 without the graph initialisation
load(ps.dlocs{dind});
[nobjects, ps] = setrunps(data, dind, ps);
[data, ps] = scaledata(data, ps);
if ~isfield(ps, 'overrideSS'), ps.overrideSS = 0; end
ps.cleanstrong = 0;
ps = structcounts(nobjects, ps);
end

function p = setmode(p, m)
p.fixedall = m(1); p.fixedinternal = m(2); p.fixedexternal = m(3); p.prodtied = m(4);
end

function spydir = make_spy(mdir)
% graph_like_orig.m = graph_like.m renamed; graph_like.m = a spy logging every 37th
% fast-mode call (<= 15 per run) and counting fast and slow calls
spydir = tempname(); mkdir(spydir);
src = fileread(fullfile(mdir, 'graph_like.m'));
src = regexprep(src, 'function \[logI graph\] = graph_like\(', ...
                'function [logI graph] = graph_like_orig(', 'once');
fid = fopen(fullfile(spydir, 'graph_like_orig.m'), 'w'); fprintf(fid, '%s', src); fclose(fid);
spy = {
  'function [logI graph] = graph_like(data, graph, ps)'
  'global SPY'
  'ingraph = graph;'
  '[logI graph] = graph_like_orig(data, graph, ps);'
  'if isfield(ps, ''fast'') && ps.fast == 1'
  '  SPY.nfast = SPY.nfast + 1;'
  '  if mod(SPY.nfast, 37) == 1 && numel(SPY.calls) < 15'
  '    q = struct(''lbeta'', ps.lbeta, ''sigbeta'', ps.sigbeta, ''missingdata'', ps.missingdata, ...'
  '      ''zglreg'', ps.zglreg, ''overrideSS'', ps.overrideSS, ''fixedall'', ps.fixedall, ...'
  '      ''fixedinternal'', ps.fixedinternal, ''fixedexternal'', ps.fixedexternal, ...'
  '      ''prodtied'', ps.prodtied, ''type'', ps.runps.type, ...'
  '      ''SS'', ps.runps.SS, ''chunkcount'', ps.runps.chunkcount);'
  '    SPY.calls{end + 1} = struct(''n'', SPY.nfast, ''graph'', ingraph, ''ps'', q, ...'
  '      ''logI'', logI, ''out'', graph);'
  '  end'
  'else'
  '  SPY.nslow = SPY.nslow + 1;'
  'end'
  'end'};
fid = fopen(fullfile(spydir, 'graph_like.m'), 'w');
fprintf(fid, '%s\n', spy{:}); fclose(fid);
end

function ll = spied_run(mdir, outdir, sind, dind)
% one feature run as in legacy/matlab/run_baseline.m (headless ps, rand('state', 1))
olddir = pwd;
cd(mdir); ps = defaultps(setps());   % setps builds ps.dlocs from pwd
ps.showtruegraph = 0; ps.showinferredgraph = 0; ps.showbestsplit = 0;
ps.showpreclean = 0; ps.showpostclean = 0;
cd(outdir);
rand('state', 1);
try
  evalc('ll = runmodel(ps, sind, dind, 1);');
catch err
  cd(olddir); rethrow(err);
end
cd(olddir);
end
