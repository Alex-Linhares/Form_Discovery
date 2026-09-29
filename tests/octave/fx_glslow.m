function fx_glslow(outfile, seedoffset)
% Fixture for item 19 (L3-b2): graph_like_conn in slow mode (graph_like_conn.m:35-110,
% fminunc + Laplace approximation).
%
% graph_like_conn is run from an instrumented copy (made in a temp dir that shadows the
% original) which leaves its intermediate values in the global GLC: Xinit, the fminunc
% optimum X and fX, [f g] = dataprobwsig(X, ...) (fg, g), the full finite-difference H
% (Hfull, before truncation), includeind, ll, the first logI (logI0, complex when
% mylogdet(inv(-H)) is), and the final logI. Only these capture lines are added; the
% code is otherwise the original.
%
% ds    the three demo feature sets after runmodel's preprocessing.
% gh    every bestgraph of the 19 feature baseline growth histories, scored by
%       graph_like with ps.fast = 0 in the file's tying mode and, for tied files, untied.
% sy    the 29 dataprob.mat graphs (10 objects, some unassigned) with random feature and
%       similarity data (runps.dim = 30) in tying modes none and fixedexternal.
% jd    9 of the dpmiss.mat graphs (every 3rd) with judges (missing-data chunk path), mode none.
% lp    the Laplace part alone (graph_like_conn.m:76-93, extracted from the source into
%       glc_laplace) at points that are not optima (Xinit of gh/sy records and a random
%       perturbation of it), so the ~isreal fallback runs.
% qd    the same Laplace code with the quadratic objective glc_quad.m at points with
%       entries above upper_bound - 5 (includeind truncation) and indefinite Hessians.
%       (Real graphs with log weights that large make chol fail in dataprobwsig.)
% bl    slow-mode graph_like calls captured by a spy in chain x demo_chain_feat and
%       tree x demo_tree_feat (run_baseline.m's settings and seed): every slow call of
%       the chain run, every 4th of the tree run, with inputs (ps fields), GLC and
%       outputs. bl_ll holds the runs' final scores.
% SEEDOFFSET (default 0) shifts the rand/randn('state') seeds of sy and lp (live test).
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
global GLC

MODES = [0 0 0 0; 0 0 1 0; 0 1 0 0; 0 1 1 0; 1 0 0 0; 0 0 0 1; 0 0 1 1; 0 1 0 1];
out.modes = MODES;

spydir = make_shadows(mdir);
addpath(spydir, '-begin');
o = optimset('fminunc');
out.fminunc_tolfun = o.TolFun; out.fminunc_tolx = o.TolX; out.fminunc_maxiter = o.MaxIter;

% --- demo feature data sets -----------------------------------------------------------
dps = {};
ds = {};
for dind = 1:3
  [data, p] = prep(ps0, dind);
  dps{dind} = p;
  ds{dind} = struct('name', ps0.data{dind}, 'data', data);
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
      p.runps.structname = g.type; p.fast = 0;
      r = struct('file', f, 'depth', k, 'data', dind, 'mode', mi, 'filemode', m, ...
                 'graph', g, 'bgll', L.bestgraphlls(k));
      gh{end + 1} = score(r, ds{dind}.data, g, p);
    end
  end
end
out.gh = gh;

% --- synthetic graphs with unassigned objects -----------------------------------------
F = load(fullfile(fxdir, 'dataprob.mat'));
sy = {};
randn('state', seedoffset + 1900); rand('state', seedoffset + 1901);
nobj = 10; nfeat = 20; simdim = 30;
for q = 1:numel(F.gr)
  g = F.gr{q}.graph;
  A = randn(nobj, simdim);
  dats = {randn(nobj, nfeat), A * A' / simdim};
  for v = 1:2
    for mi = [1 2]
      p = setmode(ps0, MODES(mi, :));
      p.missingdata = 0; p.overrideSS = 0; p.zglreg = 0; p.fast = 0;
      p.runps.chunkcount = -1; p.runps.SS = [];
      if v == 1, p.runps.type = 'feat'; else p.runps.type = 'sim'; p.runps.dim = simdim; end
      r = struct('src', F.gr{q}.src, 'graph', g, 'variant', v, 'mode', mi, 'd', dats{v});
      sy{end + 1} = score(r, dats{v}, g, p);
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
for q = 1:3:numel(D.gr)
  g = D.gr{q}.graph;
  p = setmode(pj, MODES(1, :));
  p.runps.structname = g.type; p.fast = 0;
  r = struct('src', D.gr{q}.src, 'graph', g, 'mode', 1);
  jd{end + 1} = score(r, jdata, g, p);
end
out.jd = jd;

% --- the Laplace part at non-optimal points -------------------------------------------
lp = {};
randn('state', seedoffset + 1902);
srcs = {};
for i = 1:6:numel(gh), srcs{end + 1} = {'gh', i}; end
for i = 1:4:numel(sy), srcs{end + 1} = {'sy', i}; end
for s = 1:numel(srcs)
  if strcmp(srcs{s}{1}, 'gh'), r = gh{srcs{s}{2}}; dd = ds{r.data}.data;
    p = setmode(dps{r.data}, MODES(r.mode, :)); p.runps.structname = r.graph.type;
  else r = sy{srcs{s}{2}}; dd = r.d;
    p = setmode(ps0, MODES(r.mode, :));
    p.missingdata = 0; p.overrideSS = 0; p.zglreg = 0;
    p.runps.chunkcount = -1; p.runps.SS = [];
    if r.variant == 1, p.runps.type = 'feat'; else p.runps.type = 'sim'; p.runps.dim = simdim; end
  end
  if ~isempty(r.err), continue; end
  p.fast = 0;
  gl = r.graph;
  gl.Wsym(gl.adjsym > 0) = log(gl.Wsym(gl.adjsym > 0)); gl.sigma = log(gl.sigma);
  dsub = subset(dd, gl, p);
  X0 = r.glc.Xinit;
  pts = {X0, X0 + 0.5 * randn(size(X0))};
  for k = 1:numel(pts)
    q = struct('src', srcs{s}{1}, 'ind', srcs{s}{2}, 'k', k, 'X', pts{k}, 'err', '', ...
               'logI', [], 'H', [], 'includeind', [], 'll', [], 'logI0', []);
    try
      [q.logI, q.H, q.includeind, q.ll, q.logI0] = glc_laplace(@dataprobwsig, q.X, dsub, gl, p);
    catch err
      q.err = err.message;
    end
    lp{end + 1} = q;
  end
end
out.lp = lp;

% --- the Laplace part with a quadratic objective (glc_quad.m) -------------------------
% f(x) = x'*A*x/2 - b'*x: points with entries above upper_bound - 5 (includeind
% truncation, 'sigma blows up' when x(1) is one of them, an error when all are), and
% indefinite A (the ~isreal fallback).
qd = {};
for k = 1:12
  n = 2 + mod(k, 5);
  B = randn(n); A = B * B' + n * eye(n);
  if mod(k, 3) == 0, A = A - (max(eig(A)) + min(eig(A))) / 2 * eye(n); end   % indefinite
  b = randn(n, 1);
  X = randn(n, 1);
  if k > 2, X(randperm(n)(1:1 + mod(k, n - 1))) = 195 + 3 * rand(); end
  if k == 12, X(:) = 196; end
  q = struct('k', k, 'A', A, 'b', b, 'X', X, 'err', '', 'logI', [], 'H', [], ...
             'includeind', [], 'll', [], 'logI0', []);
  try
    [q.logI, q.H, q.includeind, q.ll, q.logI0] = glc_laplace(@glc_quad, X, A, b, []);
  catch err
    q.err = err.message;
  end
  qd{end + 1} = q;
end
out.qd = qd;

% --- spied baseline runs --------------------------------------------------------------
global SPY
tmp = tempname(); mkdir(tmp);
bl = {};
out.bl_run = {}; out.bl_ll = []; out.bl_nslow = [];
runs = {{'chain', 1, 1}, {'tree', 3, 4}};
for r = 1:numel(runs)
  SPY = struct('calls', {{}}, 'nslow', 0, 'every', runs{r}{3});
  sind = find(strcmp(ps0.structures, runs{r}{1}));
  out.bl_ll(r) = spied_run(mdir, tmp, sind, runs{r}{2});
  out.bl_run{r} = [runs{r}{1} ':' ps0.data{runs{r}{2}}];
  out.bl_nslow(r) = SPY.nslow;
  for q = 1:numel(SPY.calls), SPY.calls{q}.run = r; bl{end + 1} = SPY.calls{q}; end
end
out.bl = bl;

rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function r = score(r, data, g, p)
global GLC
r.err = ''; r.logI = []; r.out = []; r.glc = [];
GLC = struct();
try
  [r.logI, r.out] = graph_like(data, g, p);
  r.glc = GLC;
catch err
  r.err = err.message;
end
end

function d = subset(d, graph, ps)
% graph_like.m:7-10
currobj = find(graph.z >= 0);
switch ps.runps.type
  case 'sim', d = d(currobj, currobj);
  case 'feat', d = d(currobj, :);
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

function p = setmode(p, m)
p.fixedall = m(1); p.fixedinternal = m(2); p.fixedexternal = m(3); p.prodtied = m(4);
end

function spydir = make_shadows(mdir)
% graph_like_conn.m with capture lines; glc_laplace.m = graph_like_conn.m:76-93 as a
% function; graph_like.m = a spy recording slow-mode calls (graph_like_orig.m = the
% original).
spydir = tempname(); mkdir(spydir);
src = fileread(fullfile(mdir, 'graph_like_conn.m'));
cap = @(s, pat, add) strrep(s, pat, [pat add]);
n0 = numel(src);
s = src;
s = cap(s, 'Xinit = [graph.sigma;Xinit];', sprintf('\nglobal GLC; GLC.Xinit = Xinit;'));
s = cap(s, 'H=-hessiangrad(datal, X, 1e-5);', sprintf('\nGLC.Hfull = H;'));
s = cap(s, 'logI = (d/2)*log(2*pi)+0.5*mylogdet(inv(-H))+ll;', sprintf('\nGLC.logI0 = logI;'));
s = strrep(s, sprintf('Xorig = exp(Xorig);'), ...
           sprintf(['GLC.X = X; GLC.fX = fX; GLC.includeind = includeind; GLC.ll = ll; ' ...
                    'GLC.logI = logI;\n[GLC.fg, GLC.g] = dprobfun(X, data, graphL, ps);\n' ...
                    'Xorig = exp(Xorig);']));
% the fast-mode block also has 'Xinit = [graph.sigma;Xinit];' -- harmless there
assert(numel(strfind(s, 'GLC.')) == 11 && numel(s) > n0);
fid = fopen(fullfile(spydir, 'graph_like_conn.m'), 'w'); fprintf(fid, '%s', s); fclose(fid);

i0 = strfind(src, 'll = -feval(dprobfun, X, data, graphL, ps);');
i1 = strfind(src, 'Xorig = exp(Xorig);');
assert(numel(i0) == 1 && numel(i1) == 1);
body = src(i0:i1 - 1);
body = cap(body, 'logI = (d/2)*log(2*pi)+0.5*mylogdet(inv(-H))+ll;', sprintf('\nlogI0 = logI;'));
body = cap(body, 'H=-hessiangrad(datal, X, 1e-5);', sprintf('\nHfull = H;'));
lap = sprintf(['function [logI, Hfull, includeind, ll, logI0] = glc_laplace(dprobfun, X, data, graphL, ps)\n' ...
               '%% graph_like_conn.m:76-93 (extracted by fx_glslow.m)\n' ...
               'upper_bound = 200;\n%s\nend\n'], body);
fid = fopen(fullfile(spydir, 'glc_laplace.m'), 'w'); fprintf(fid, '%s', lap); fclose(fid);

src = fileread(fullfile(mdir, 'graph_like.m'));
src = regexprep(src, 'function \[logI graph\] = graph_like\(', ...
                'function [logI graph] = graph_like_orig(', 'once');
fid = fopen(fullfile(spydir, 'graph_like_orig.m'), 'w'); fprintf(fid, '%s', src); fclose(fid);
spy = {
  'function [logI graph] = graph_like(data, graph, ps)'
  'global SPY GLC'
  'ingraph = graph;'
  'GLC = struct();'
  '[logI graph] = graph_like_orig(data, graph, ps);'
  'if ~isempty(SPY) && ~(isfield(ps, ''fast'') && ps.fast == 1)'
  '  SPY.nslow = SPY.nslow + 1;'
  '  if mod(SPY.nslow - 1, SPY.every) == 0'
  '    q = struct(''lbeta'', ps.lbeta, ''sigbeta'', ps.sigbeta, ''missingdata'', ps.missingdata, ...'
  '      ''zglreg'', ps.zglreg, ''overrideSS'', ps.overrideSS, ''fixedall'', ps.fixedall, ...'
  '      ''fixedinternal'', ps.fixedinternal, ''fixedexternal'', ps.fixedexternal, ...'
  '      ''prodtied'', ps.prodtied, ''type'', ps.runps.type, ...'
  '      ''SS'', ps.runps.SS, ''chunkcount'', ps.runps.chunkcount);'
  '    SPY.calls{end + 1} = struct(''n'', SPY.nslow, ''graph'', ingraph, ''ps'', q, ...'
  '      ''logI'', logI, ''out'', graph, ''glc'', GLC);'
  '  end'
  'end'
  'end'};
fid = fopen(fullfile(spydir, 'graph_like.m'), 'w');
fprintf(fid, '%s\n', spy{:}); fclose(fid);
end

function ll = spied_run(mdir, outdir, sind, dind)
% one feature run as in matlab/run_baseline.m (headless ps, rand('state', 1))
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
