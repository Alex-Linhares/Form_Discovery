function fx_dpmiss(outfile, seedoffset)
% Fixture for item 17 (L3-a2): the dataprobwsig missing-data chunk path
% (dataprobwsig.m:24-60) on the judges data (13 objects, 38 chunks).
%
% data   judges after setrunps/scaledata (Inf = missing); chunks in pj.runps
%        (chunknum, objind, featind, chunksize, chunkSS).
% gr     graphs over judges' 13 objects with random weights (fx_dataprob.m's randw):
%        makeemptygraph (one cluster) for chain, and seeded split_node sequences (the
%        graphs after steps 2, 4, 6) for chain, ring, tree, hierarchy, partition,
%        connected, grid and cylinder (every step for tree and hierarchy), plus graphs with unassigned objects after step 3
%        (empty_graph + two add_element calls, as in best_split.m:26-32).
% cs     for every graph and each of the 8 tying modes of MODES
%        (fixedall fixedinternal fixedexternal prodtied):
%          d = data(g.z > 0, :)  (as graph_like.m:7-10 passes it);
%          Wvec = log of random weights, length 1 + length(mat2vec(...));
%          [ll dW] = dataprobwsig(Wvec, d, g, p); ll1 = dataprobwsig(...) (nargout 1);
%          cg = checkgrad('dataprobwsig', Wvec, 1e-5, d, g, p) (mode 1 and fixedexternal);
%        or Octave's error message. For the first SPYCASES mode-1 cases, every recursive
%        per-chunk call (ps.missingdata = 0) is recorded by a spy in ch: its inputs
%        (Wvec, d, graph, runps.SS, runps.chunkcount) and outputs (ll, dW, dWp).
% bl     outer (ps.missingdata = 1) dataprobwsig calls captured by the same spy while
%        re-running partition x judges with run_baseline.m's settings and seed (every 53rd
%        call, at most 8 with nargout 1, and every 29th gradient call, at most 8): Wvec,
%        graph, nargout, the scalar ps fields, the outputs, and whether d equals data(find(graph.z > 0), :) and the chunk fields equal pj's.
%        bl_ll is the run's final score.
% err3   Octave's message for [ll dW dWp] = dataprobwsig(...) on the chunk path (MATLAB
%        never sets dWvecprior there).
% SEEDOFFSET (default 0) shifts the rand('state') seeds (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
addpath(mdir);
ps = defaultps(setps());
out = struct();
more off;

MODES = [0 0 0 0; 0 0 1 0; 0 1 0 0; 0 1 1 0; 1 0 0 0; 0 0 0 1; 0 0 1 1; 0 1 0 1];
SPYCASES = 6;
out.modes = MODES;

L = load(fullfile(mdir, 'data', 'judges.mat'));
[~, pj] = setrunps(L.data, 13, ps);
[data, pj] = scaledata(L.data, pj);
pj.overrideSS = 0;   % as runmodel.m:79-81
out.data = data;
out.chunknum = pj.runps.chunknum;
nobj = size(data, 1);

% --- graphs ---------------------------------------------------------------------------
graphs = {}; gsrc = {};
p = pj; p.runps.structname = 'chain'; p.runps.nobjects = nobj;
graphs{end + 1} = makeemptygraph(p); gsrc{end + 1} = 'chain:empty';
seqnames = {'chain', 'ring', 'tree', 'hierarchy', 'partition', 'connected', 'grid', 'cylinder'};
for s = 1:numel(seqnames)
  p = pj; p.runps.structname = seqnames{s}; p.runps.nobjects = nobj;
  g = makeemptygraph(p);
  rand('state', seedoffset + 1000 + s);
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
    if any(step == [2 4 6]) || any(strcmp(seqnames{s}, {'tree', 'hierarchy'}))
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
rand('state', seedoffset + 1100);
for q = 1:numel(graphs)
  gr{end + 1} = struct('src', gsrc{q}, 'graph', randw(graphs{q}));
end
out.gr = gr;

% --- cases ----------------------------------------------------------------------------
spydir = make_spy(mdir);
addpath(spydir, '-begin');
global SPY
SPY = struct('on', 0, 'calls', {{}}, 'bl', 0, 'n', 0, 'blcalls', {{}}, 'data', data, ...
             'pj', pj);
cs = {}; ch = {};
rand('state', seedoffset + 1200);
nspied = 0;
for q = 1:numel(gr)
  g = gr{q}.graph;
  d = data(g.z > 0, :);
  for mi = 1:size(MODES, 1)
    p = setmode(pj, MODES(mi, :));
    r = struct('graph', q, 'mode', mi, 'Wvec', [], 'err', '', 'll', [], 'dW', [], ...
               'll1', [], 'cg', [], 'spied', 0);
    nw = 0;
    try
      gl = g; gl.Wsym(gl.adjsym > 0) = log(gl.Wsym(gl.adjsym > 0));
      nw = numel(mat2vec(gl.Wsym, gl, p));
    catch err
      r.err = ['mat2vec: ' err.message];
    end
    if isempty(r.err)
      r.Wvec = log(0.5 + rand(nw + 1, 1));
      spy = mi == 1 && nspied < SPYCASES;
      try
        SPY.on = spy; SPY.calls = {};
        [r.ll, r.dW] = dataprobwsig(r.Wvec, d, g, p);
        SPY.on = 0;
        r.ll1 = dataprobwsig(r.Wvec, d, g, p);
        if mi == 1 || p.fixedexternal
          evalc('r.cg = checkgrad(''dataprobwsig'', r.Wvec, 1e-5, d, g, p);');
        end
      catch err
        SPY.on = 0;
        r.err = err.message;
      end
      if spy && isempty(r.err)
        nspied = nspied + 1; r.spied = nspied;
        for k = 1:numel(SPY.calls)
          SPY.calls{k}.case = numel(cs) + 1; SPY.calls{k}.chunk = k;
          ch{end + 1} = SPY.calls{k};
        end
      end
    end
    cs{end + 1} = r;
  end
end
out.cs = cs;
out.ch = ch;

% the chunk path never sets dWvecprior
g = gr{1}.graph;
try
  [a, b, c] = dataprobwsig(log(0.5 + ones(2 + nobj, 1)), data, g, pj);
  out.err3 = '';
catch err
  out.err3 = err.message;
end
% spied real run: partition x judges
tmp = tempname(); mkdir(tmp);
SPY.on = 0; SPY.bl = 1; SPY.n = 0; SPY.n2 = 0; SPY.k1 = 0; SPY.k2 = 0; SPY.blcalls = {};
out.bl_ll = spied_run(tmp, find(strcmp(ps.structures, 'partition')), 13);
SPY.bl = 0;
out.bl = SPY.blcalls;
out.bl_ncalls = [SPY.n, SPY.n2];
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function p = setmode(p, m)
p.fixedall = m(1); p.fixedinternal = m(2); p.fixedexternal = m(3); p.prodtied = m(4);
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

function ll = spied_run(outdir, sind, dind)
% one run as in legacy/matlab/run_baseline.m (headless ps, rand('state', 1))
olddir = pwd;
mdir = fileparts(which('setps'));
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
% dataprobwsig_orig.m = dataprobwsig.m renamed; its recursive calls (dataprobwsig.m:45,55)
% still go through dataprobwsig.m, a spy that records every call made with
% ps.missingdata == 0 while SPY.on is set.
spydir = tempname(); mkdir(spydir);
src = fileread(fullfile(mdir, 'dataprobwsig.m'));
src = regexprep(src, '^function \[ll dWvec dWvecprior\] = dataprobwsig\(', ...
                'function [ll dWvec dWvecprior] = dataprobwsig_orig(', 'once', 'lineanchors');
fid = fopen(fullfile(spydir, 'dataprobwsig_orig.m'), 'w'); fprintf(fid, '%s', src); fclose(fid);
spy = {
  'function [ll dWvec dWvecprior] = dataprobwsig(Wvec, d, graph, ps)'
  'global SPY'
  'dWvec = []; dWvecprior = [];'
  'if nargout > 2'
  '  [ll dWvec dWvecprior] = dataprobwsig_orig(Wvec, d, graph, ps);'
  'elseif nargout > 1'
  '  [ll dWvec] = dataprobwsig_orig(Wvec, d, graph, ps);'
  'else'
  '  ll = dataprobwsig_orig(Wvec, d, graph, ps);'
  'end'
  'if SPY.on && ~ps.missingdata'
  '  SPY.calls{end + 1} = struct(''nargout'', nargout, ''Wvec'', Wvec, ''d'', d, ...'
  '    ''graph'', graph, ''SS'', ps.runps.SS, ''chunkcount'', ps.runps.chunkcount, ...'
  '    ''ll'', ll, ''dW'', dWvec, ''dWp'', dWvecprior);'
  'end'
  'if SPY.bl && ps.missingdata'
  '  SPY.n = SPY.n + 1; SPY.n2 = SPY.n2 + (nargout > 1);'
  '  if (mod(SPY.n, 53) == 1 && SPY.k1 < 8) || (nargout > 1 && mod(SPY.n2, 29) == 1 && SPY.k2 < 8)'
  '    SPY.k1 = SPY.k1 + (nargout == 1); SPY.k2 = SPY.k2 + (nargout > 1);'
  '    currobj = find(graph.z > 0);'
  '    r = SPY.pj.runps;'
  '    samechunks = isequal(ps.runps.objind, r.objind) && isequal(ps.runps.featind, r.featind) ...'
  '      && isequal(ps.runps.chunkSS, r.chunkSS) && isequal(ps.runps.chunksize, r.chunksize);'
  '    q = struct(''lbeta'', ps.lbeta, ''sigbeta'', ps.sigbeta, ''zglreg'', ps.zglreg, ...'
  '      ''overrideSS'', ps.overrideSS, ''fixedall'', ps.fixedall, ''fixedinternal'', ps.fixedinternal, ...'
  '      ''fixedexternal'', ps.fixedexternal, ''prodtied'', ps.prodtied, ''type'', ps.runps.type);'
  '    SPY.blcalls{end + 1} = struct(''n'', SPY.n, ''nargout'', nargout, ''Wvec'', Wvec, ...'
  '      ''graph'', graph, ''ps'', q, ''dsame'', isequal(d, SPY.data(currobj, :)), ...'
  '      ''samechunks'', samechunks, ''ll'', ll, ''dW'', dWvec);'
  '  end'
  'end'
  'end'};
fid = fopen(fullfile(spydir, 'dataprobwsig.m'), 'w');
fprintf(fid, '%s\n', spy{:}); fclose(fid);
end
