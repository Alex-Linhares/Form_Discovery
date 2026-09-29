function fx_dataprob(outfile, seedoffset)
% Fixture for item 16 (L3-a1): inv_covariance, gplike, dataprobwsig (no missing-data
% chunk path), checkgrad.
%
% gr    graphs over 10 objects: makeemptygraph (one cluster) for chain and grid, and seeded
%       split_node sequences (the graphs after steps 2, 4, 6 that succeed; every step for
%       partition and hierarchy) for chain, ring, tree, hierarchy, partition, connected,
%       grid and cylinder, plus graphs with unassigned objects
%       (empty_graph + two add_element calls, as in best_split.m:26-32). Random positive
%       weights on graph Wsym and component W/Wsym (as fx_weights.m's 'rw' variant).
% dat   data sets, one per (graph, variant): 'feat' (10 x 20, chunkcount -1, so
%       dataprobwsig/gplike use d*d'), 'featSS' (chunkcount 10 with a random SPD
%       runps.SS, which both must use), 'sim' (10 x 10 similarity, runps.dim = 30),
%       'featz' ('feat' with ps.zglreg = 1), 'miss' / 'simmiss' / 'missz' (only the first
%       7 rows, so nmiss = 3 and dataprobwsig.m:155-236 runs).
% cs    for every graph, the 7 variants in tying mode 1 (none) and 'feat'/'miss' in the
%       other 7 modes of MODES (fixedall fixedinternal fixedexternal prodtied):
%         Wvec = log of random weights, length 1 + length(mat2vec(...));
%         [ll dW dWp] = dataprobwsig(Wvec, d, g, p); ll1 = dataprobwsig(...) (nargout 1);
%         cg = checkgrad('dataprobwsig', Wvec, 1e-5, d, g, p);
%         J/L = inv_covariance(cw.Wsym, nobj, sigma, p) for cw = combineWs(g, exp(Wvec(2:end)));
%         gp = gplike(d, inv_posdef(J), dim, p).
%       Each stores its outputs or Octave's error message.
% ic    inv_covariance on random symmetric W (with isolated 'hole' nodes), zglreg 0/1.
% bl_*  dataprobwsig calls captured by a spy while re-running the feature baselines
%       chain x demo_chain_feat, ring x demo_ring_feat and tree x demo_tree_feat
%       (run_baseline.m's settings and seed; every 97th call, at most 12 per run). The
%       data matrix is stored once per run (bl_data); bl_ll holds each run's final score.
% SEEDOFFSET (default 0) shifts the rand/randn('state') seeds (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'matlab', 'formdiscovery1.0');
addpath(mdir);
ps = defaultps(setps());
ps.missingdata = 0; ps.overrideSS = 0; ps.runps.type = 'feat';
out = struct();
more off;

MODES = [0 0 0 0; 0 0 1 0; 0 1 0 0; 0 1 1 0; 1 0 0 0; 0 0 0 1; 0 0 1 1; 0 1 0 1];
VARIANTS = {'feat', 'featSS', 'sim', 'featz', 'miss', 'simmiss', 'missz'};
out.modes = MODES;
out.variants = VARIANTS;

% --- graphs ---------------------------------------------------------------------------
nobj = 10; nfeat = 20; nobs = 7; simdim = 30;
graphs = {}; gsrc = {};
for name = {'chain', 'grid'}
  p = ps; p.runps.structname = name{1}; p.runps.nobjects = nobj;
  graphs{end + 1} = makeemptygraph(p); gsrc{end + 1} = [name{1} ':empty'];
end
seqnames = {'chain', 'ring', 'tree', 'hierarchy', 'partition', 'connected', 'grid', 'cylinder'};
for s = 1:numel(seqnames)
  p = ps; p.runps.structname = seqnames{s}; p.runps.nobjects = nobj;
  g = makeemptygraph(p);
  rand('state', seedoffset + 600 + s);
  for step = 1:6
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
    if any(step == [2 4 6]) || any(strcmp(seqnames{s}, {'partition', 'hierarchy'}))
      graphs{end + 1} = g; gsrc{end + 1} = sprintf('%s:%d', seqnames{s}, step);
    end
    if step == 3 && ~isempty(part2) && numel(members) >= 3
      e = empty_graph(g, i, c1, c2);
      e = add_element(e, i, c1, part1(1), p);
      e = add_element(e, i, c2, part2(1), p);
      graphs{end + 1} = e; gsrc{end + 1} = sprintf('%s:%d:missing', seqnames{s}, step);
    end
  end
end
gr = {};
rand('state', seedoffset + 700);
for q = 1:numel(graphs)
  gr{end + 1} = struct('src', gsrc{q}, 'graph', randw(graphs{q}));
end
out.gr = gr;

% --- data sets and cases --------------------------------------------------------------
dat = {}; cs = {};
randn('state', seedoffset + 800); rand('state', seedoffset + 801);
for q = 1:numel(gr)
  g = gr{q}.graph;
  dind = zeros(1, numel(VARIANTS));
  for v = 1:numel(VARIANTS)
    [d, SS] = makedata(VARIANTS{v}, nobj, nfeat, nobs, simdim);
    dat{end + 1} = struct('variant', VARIANTS{v}, 'd', d, 'SS', SS);
    dind(v) = numel(dat);
  end
  for mi = 1:size(MODES, 1)
    if mi == 1, vs = 1:numel(VARIANTS); else vs = [1 5]; end
    for v = vs
      p = setmode(ps, MODES(mi, :));
      p = setvariant(p, VARIANTS{v}, nobj, simdim, dat{dind(v)}.SS);
      d = dat{dind(v)}.d;
      r = struct('graph', q, 'mode', mi, 'variant', v, 'data', dind(v), 'Wvec', [], ...
                 'err', '', 'll', [], 'dW', [], 'dWp', [], 'll1', [], 'cg', [], ...
                 'J', [], 'L', [], 'gp', [], 'gperr', '');
      nw = 0;
      try
        gl = g; gl.Wsym(gl.adjsym > 0) = log(gl.Wsym(gl.adjsym > 0));
        nw = numel(mat2vec(gl.Wsym, gl, p));
      catch err
        r.err = ['mat2vec: ' err.message];
      end
      if isempty(r.err)
        r.Wvec = log(0.5 + rand(nw + 1, 1));
        try
          [r.ll, r.dW, r.dWp] = dataprobwsig(r.Wvec, d, g, p);
          r.ll1 = dataprobwsig(r.Wvec, d, g, p);
          evalc('r.cg = checkgrad(''dataprobwsig'', r.Wvec, 1e-5, d, g, p);');
        catch err
          r.err = err.message;
        end
        try
          sigma = exp(r.Wvec(1));
          cw = combineWs(g, exp(r.Wvec(2:end)), p);
          [r.J, r.L] = inv_covariance(cw.Wsym, g.objcount, sigma, p);
          if strcmp(p.runps.type, 'sim'), dim = p.runps.dim; else dim = size(d, 2); end
          r.gp = gplike(d, inv_posdef(r.J), dim, p);
        catch err
          r.gperr = err.message;
        end
      end
      cs{end + 1} = r;
    end
  end
end
out.dat = dat;
out.cs = cs;

% --- inv_covariance on random W with holes ---------------------------------------------
ic = {};
rand('state', seedoffset + 900);
for k = 1:12
  n = 5 + mod(k, 4) * 2; no = 3 + mod(k, 3);
  R = rand(n); W = triu(R, 1) + triu(R, 1)';
  W(rand(n) < 0.3) = 0; W = triu(W, 1) + triu(W, 1)';
  holes = unique(1 + floor(rand(1, 1 + mod(k, 2)) * n));
  W(holes, :) = 0; W(:, holes) = 0;
  if mod(k, 3) == 0, W(1, 2) = 0.7; end   % one asymmetric entry
  sigma = 0.3 + rand();
  for z = 0:1
    p = ps; p.zglreg = z;
    [J, L] = inv_covariance(W, no, sigma, p);
    ic{end + 1} = struct('W', W, 'nobj', no, 'sigma', sigma, 'zglreg', z, 'J', J, 'L', L);
  end
end
out.ic = ic;

% --- spied baseline runs --------------------------------------------------------------
spydir = make_spy(mdir);
addpath(spydir, '-begin');
global SPY
tmp = tempname(); mkdir(tmp);
bl = {};
out.bl_run = {}; out.bl_ll = []; out.bl_data = {};
snames = {'chain', 'ring', 'tree'};
for r = 1:3
  SPY = struct('calls', {{}}, 'n', 0, 'd', []);
  sind = find(strcmp(ps.structures, snames{r}));
  out.bl_ll(r) = spied_run(mdir, tmp, sind, r);
  out.bl_run{r} = [ps.structures{sind} ':' ps.data{r}];
  out.bl_data{r} = SPY.d;
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

function p = setmode(p, m)
p.fixedall = m(1); p.fixedinternal = m(2); p.fixedexternal = m(3); p.prodtied = m(4);
end

function [d, SS] = makedata(variant, nobj, nfeat, nobs, simdim)
SS = [];
switch variant
  case {'sim', 'simmiss'}
    A = randn(nobj, simdim); d = A * A' / simdim;
  otherwise
    d = randn(nobj, nfeat);
end
if strcmp(variant, 'featSS')
  A = randn(nobj, 2 * nobj); SS = A * A' / (2 * nobj);
end
if any(strcmp(variant, {'miss', 'simmiss', 'missz'}))
  d = d(1:nobs, :);
  if strcmp(variant, 'simmiss'), d = d(:, 1:nobs); end
end
end

function p = setvariant(p, variant, nobj, simdim, SS)
p.zglreg = any(strcmp(variant, {'featz', 'missz'}));
p.runps.chunkcount = -1; p.runps.SS = [];
if any(strcmp(variant, {'sim', 'simmiss'}))
  p.runps.type = 'sim'; p.runps.dim = simdim;
else
  p.runps.type = 'feat';
end
if strcmp(variant, 'featSS')
  p.runps.chunkcount = nobj; p.runps.SS = SS;
end
end

function g = randweights_sym(A)
R = 0.5 + rand(size(A));
R = triu(R) + triu(R, 1)';
g = double(A > 0) .* R;
end

function g = randw(g)
g.Wsym = randweights_sym(g.adjsym);
for j = 1:g.ncomp
  g.components{j}.Wsym = randweights_sym(g.components{j}.adjsym);
  g.components{j}.W = g.components{j}.adj .* g.components{j}.Wsym;
end
g.extlen = 0.5 + rand(); g.intlen = 0.5 + rand();
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

function spydir = make_spy(mdir)
% dataprobwsig_orig.m = dataprobwsig.m renamed (its recursive call, dataprobwsig.m:45/55,
% still goes through the spy); dataprobwsig.m = a spy logging every 97th call (<= 12)
spydir = tempname(); mkdir(spydir);
src = fileread(fullfile(mdir, 'dataprobwsig.m'));
src = regexprep(src, '=\s*dataprobwsig\(', '= dataprobwsig_orig(', 'once');
fid = fopen(fullfile(spydir, 'dataprobwsig_orig.m'), 'w'); fprintf(fid, '%s', src); fclose(fid);
spy = {
  'function [ll dWvec dWvecprior] = dataprobwsig(Wvec, d, graph, ps)'
  'global SPY'
  'dWvec = []; dWvecprior = [];'
  'if nargout > 1'
  '  [ll dWvec dWvecprior] = dataprobwsig_orig(Wvec, d, graph, ps);'
  'else'
  '  ll = dataprobwsig_orig(Wvec, d, graph, ps);'
  'end'
  'SPY.n = SPY.n + 1;'
  'if mod(SPY.n, 97) == 1 && numel(SPY.calls) < 12'
  '  if isempty(SPY.d), SPY.d = d; end'
  '  dsame = isequal(d, SPY.d); dd = d; if dsame, dd = []; end'
  '  if isfield(ps.runps, ''dim''), dim = ps.runps.dim; else dim = []; end'
  '  q = struct(''lbeta'', ps.lbeta, ''sigbeta'', ps.sigbeta, ''missingdata'', ps.missingdata, ...'
  '    ''zglreg'', ps.zglreg, ''overrideSS'', ps.overrideSS, ''fixedall'', ps.fixedall, ...'
  '    ''fixedinternal'', ps.fixedinternal, ''fixedexternal'', ps.fixedexternal, ...'
  '    ''prodtied'', ps.prodtied, ''type'', ps.runps.type, ''dim'', dim, ...'
  '    ''SS'', ps.runps.SS, ''chunkcount'', ps.runps.chunkcount);'
  '  SPY.calls{end + 1} = struct(''n'', SPY.n, ''nargout'', nargout, ''Wvec'', Wvec, ...'
  '    ''dsame'', dsame, ''d'', dd, ''graph'', graph, ''ps'', q, ''ll'', ll, ...'
  '    ''dW'', dWvec, ''dWp'', dWvecprior);'
  'end'
  'end'};
fid = fopen(fullfile(spydir, 'dataprobwsig.m'), 'w');
fprintf(fid, '%s\n', spy{:}); fclose(fid);
end
