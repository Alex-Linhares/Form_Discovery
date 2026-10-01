function fx_weights(outfile, seedoffset)
% Fixture for item 15 (L2-b2): mat2vec, combineWs, extract_weights.
%
% gr    graphs over 10 objects: makeemptygraph (one cluster) for chain and grid, and seeded
%       split_node sequences (6 steps) for chain, ring, tree, hierarchy, partition,
%       connected, grid and cylinder, including graphs with unassigned objects
%       (empty_graph + two add_element calls, as in best_split.m:26-32). Each graph comes
%       in two variants: 'raw' (as combinegraphs left it: the cluster block of Wsym is
%       Wcluster, not symmetrised) and 'rw' (graph Wsym, component W/Wsym, extlen and
%       intlen set to random positive weights on the edges), plus 'zw' (the 'rw' graph with
%       the first component's W/Wsym zeroed, for graphs where it has edges).
% rt    for every graph and each of the 8 tying modes in MODES (fixedall, fixedinternal,
%       fixedexternal, prodtied flags):
%         v0  = mat2vec(g.Wsym, g, p);
%         Wvec = 0.5 + rand(size(v0));  cw = combineWs(g, Wvec, p);
%         v1  = mat2vec(cw.Wsym with log weights, cw, p)   (as graph_like_conn.m:7,41);
%         [dW, dWp] = extract_weights(0, Wb, Wbp, Wd, Wdp, cw, p) on seeded random
%         gradient matrices (nobj x nlat and nlat x nlat).
%       Each step stores its output or Octave's error message.
% bl_*  mat2vec / combineWs / extract_weights calls captured by spies while re-running the
%       feature baselines chain x demo_chain_feat, ring x demo_ring_feat and
%       tree x demo_tree_feat (run_baseline.m's settings and seed; at most 6 calls per
%       function and tying mode per run). bl_ll holds each run's final score.
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

% fixedall fixedinternal fixedexternal prodtied
MODES = [0 0 0 0; 0 0 1 0; 0 1 0 0; 0 1 1 0; 1 0 0 0; 0 0 0 1; 0 0 1 1; 0 1 0 1];
out.modes = MODES;

% --- graphs ---------------------------------------------------------------------------
nobj = 10;
graphs = {}; gsrc = {};
for name = {'chain', 'grid'}
  p = ps; p.runps.structname = name{1}; p.runps.nobjects = nobj; p.runps.type = 'feat';
  graphs{end + 1} = makeemptygraph(p); gsrc{end + 1} = [name{1} ':empty'];
end
seqnames = {'chain', 'ring', 'tree', 'hierarchy', 'partition', 'connected', 'grid', 'cylinder'};
for s = 1:numel(seqnames)
  p = ps; p.runps.structname = seqnames{s}; p.runps.nobjects = nobj; p.runps.type = 'feat';
  g = makeemptygraph(p);
  rand('state', seedoffset + 300 + s);
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
    graphs{end + 1} = g; gsrc{end + 1} = sprintf('%s:%d', seqnames{s}, step);
    if any(step == [3 5]) && ~isempty(part2) && numel(members) >= 3
      e = empty_graph(g, i, c1, c2);
      e = add_element(e, i, c1, part1(1), p);
      e = add_element(e, i, c2, part2(1), p);
      graphs{end + 1} = e; gsrc{end + 1} = sprintf('%s:%d:missing', seqnames{s}, step);
    end
  end
end
gr = {};
rand('state', seedoffset + 400);
for q = 1:numel(graphs)
  gr{end + 1} = struct('src', gsrc{q}, 'variant', 'raw', 'graph', graphs{q});
  gr{end + 1} = struct('src', gsrc{q}, 'variant', 'rw', 'graph', randw(graphs{q}));
  if any(graphs{q}.components{1}.adjsym(:))
    % mat2vec.m:25 skips a prodtied component whose Wsym sums to 0
    g = gr{end}.graph; g.components{1}.Wsym(:) = 0; g.components{1}.W(:) = 0;
    gr{end + 1} = struct('src', gsrc{q}, 'variant', 'zw', 'graph', g);
  end
end
out.gr = gr;

% --- round trips ----------------------------------------------------------------------
rt = {};
randn('state', seedoffset + 500);
for q = 1:numel(gr)
  g = gr{q}.graph;
  nlat = size(g.adjcluster, 1); no = g.objcount;
  for mi = 1:size(MODES, 1)
    p = setmode(ps, MODES(mi, :));
    r = struct('graph', q, 'mode', mi, 'v0', [], 'v0err', '', 'Wvec', [], 'cw', 0, ...
               'cwerr', '', 'v1', [], 'v1err', '', 'Wb', randn(no, nlat), ...
               'Wbp', randn(no, nlat), 'Wd', randn(nlat), 'Wdp', randn(nlat), ...
               'dW', [], 'dWp', [], 'ewerr', '');
    try
      r.v0 = mat2vec(g.Wsym, g, p);
    catch err
      r.v0err = err.message;
    end
    if isempty(r.v0err)
      r.Wvec = 0.5 + rand(size(r.v0));
      try
        r.cw = combineWs(g, r.Wvec, p);
      catch err
        r.cwerr = err.message;
      end
    end
    if isstruct(r.cw)
      gl = r.cw;
      gl.Wsym(gl.adjsym > 0) = log(gl.Wsym(gl.adjsym > 0));
      try
        r.v1 = mat2vec(gl.Wsym, gl, p);
      catch err
        r.v1err = err.message;
      end
      try
        [r.dW, r.dWp] = extract_weights(zeros(no), r.Wb, r.Wbp, r.Wd, r.Wdp, r.cw, p);
      catch err
        r.ewerr = err.message;
      end
    end
    rt{end + 1} = r;
  end
end
out.rt = rt;

% --- spied baseline runs --------------------------------------------------------------
spydir = make_spies(mdir);
addpath(spydir, '-begin');
global SPY
runs = {};
for sname = {'chain', 'ring', 'tree'}
  runs{end + 1} = find(strcmp(ps.structures, sname{1}));
end
tmp = tempname(); mkdir(tmp);
bl = {};
out.bl_run = {}; out.bl_ll = []; out.bl_sind = []; out.bl_dind = [];
for r = 1:numel(runs)
  SPY = struct('calls', {{}}, 'n', zeros(3, 16));
  sind = runs{r}; dind = r;
  out.bl_ll(r) = spied_run(mdir, tmp, sind, dind);
  out.bl_run{r} = [ps.structures{sind} ':' ps.data{dind}];
  out.bl_sind(r) = sind; out.bl_dind(r) = dind;
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

function g = randweights_sym(A)
% random positive symmetric weights on the edges of the symmetric pattern A
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

function spydir = make_spies(mdir)
% <f>_orig.m = <f>.m with the function renamed; <f>.m = a spy that logs capped calls
% (at most 6 per function and tying mode fixedall + 2*fixedinternal + 4*fixedexternal +
% 8*prodtied)
spydir = tempname(); mkdir(spydir);
for f = {'mat2vec', 'combineWs', 'extract_weights'}
  src = fileread(fullfile(mdir, [f{1} '.m']));
  src = regexprep(src, ['=\s*' f{1} '\('], ['= ' f{1} '_orig('], 'once');
  fid = fopen(fullfile(spydir, [f{1} '_orig.m']), 'w'); fprintf(fid, '%s', src); fclose(fid);
end
key = 'k = 1 + ps.fixedall + 2*ps.fixedinternal + 4*ps.fixedexternal + 8*ps.prodtied;';
mode = '''mode'', [ps.fixedall ps.fixedinternal ps.fixedexternal ps.prodtied]';
spy.mat2vec = {
  'function V = mat2vec(W, graph, ps)'
  'global SPY'
  'V = mat2vec_orig(W, graph, ps);'
  key
  'if SPY.n(1, k) < 6'
  '  SPY.n(1, k) = SPY.n(1, k) + 1;'
  ['  SPY.calls{end + 1} = struct(''fn'', ''mat2vec'', ' mode ', ''W'', W, ''graph'', graph, ...']
  '    ''Wvec'', [], ''Wb'', [], ''Wbp'', [], ''Wd'', [], ''Wdp'', [], ''out'', V, ''out2'', []);'
  'end'
  'end'};
spy.combineWs = {
  'function [graph ps] = combineWs(graph, Wvec, ps)'
  'global SPY'
  'gin = graph;'
  '[graph ps] = combineWs_orig(graph, Wvec, ps);'
  key
  'if SPY.n(2, k) < 6'
  '  SPY.n(2, k) = SPY.n(2, k) + 1;'
  ['  SPY.calls{end + 1} = struct(''fn'', ''combineWs'', ' mode ', ''W'', [], ''graph'', gin, ...']
  '    ''Wvec'', Wvec, ''Wb'', [], ''Wbp'', [], ''Wd'', [], ''Wdp'', [], ''out'', graph, ''out2'', []);'
  'end'
  'end'};
spy.extract_weights = {
  'function [dWvec dWvecprior] = extract_weights(dEdlWa, dEdlWb, dEdlWbprior, dEdlWddata, dEdlWdprior, graph, ps)'
  'global SPY'
  '[dWvec dWvecprior] = extract_weights_orig(dEdlWa, dEdlWb, dEdlWbprior, dEdlWddata, dEdlWdprior, graph, ps);'
  key
  'if SPY.n(3, k) < 6'
  '  SPY.n(3, k) = SPY.n(3, k) + 1;'
  ['  SPY.calls{end + 1} = struct(''fn'', ''extract_weights'', ' mode ', ''W'', [], ''graph'', graph, ...']
  '    ''Wvec'', [], ''Wb'', dEdlWb, ''Wbp'', dEdlWbprior, ''Wd'', dEdlWddata, ''Wdp'', dEdlWdprior, ...'
  '    ''out'', dWvec, ''out2'', dWvecprior);'
  'end'
  'end'};
for f = fieldnames(spy)'
  fid = fopen(fullfile(spydir, [f{1} '.m']), 'w');
  fprintf(fid, '%s\n', spy.(f{1}){:}); fclose(fid);
end
end
