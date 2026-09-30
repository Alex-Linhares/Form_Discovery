function fx_perf(outfile, sections)
% Fixture for item 35 (PLAN.md 7.4, performance budget): Octave timings of graph_like and
% dataprobwsig per call and of structurefit per depth, with the values they return so
% that the Python side (tools/bench_perf.py, tests/test_perf.py) can check it timed the
% same computation. Timings are wall-clock seconds on the machine that generated the
% fixture; they are recorded, not compared by the gate.
%
% gl    one record per benchmark graph:
%         feature demos: the final graph of chain, ring and tree x demo_chain_feat,
%         demo_ring_feat, demo_tree_feat (tests/fixtures/baseline/feat/resultsdemo.mat);
%         synthetic: the final graph of chain x synthchain, tree x synthtree and
%         grid x synthgrid (tests/fixtures/paperlevel.mat, speed-5 runs, 78-89 nodes);
%         relational: dirring x demo_ring_rel_bin, dirhierarchy x
%         demo_hierarchy_rel_bin, order x demo_order_rel_freq
%         (tests/fixtures/baseline/rel/resultsdemo.mat).
%       All untied (fixedall = fixedinternal = fixedexternal = prodtied = 0), data after
%       runmodel's preprocessing. Timed (see timeit): graph_like with ps.fast = 1
%       (fast, t_fast), graph_like with ps.fast = 0 (slow: fminunc + Laplace, t_slow;
%       feature data only), and dataprobwsig(Xinit, data, graph, ps) with two outputs at
%       the fast-mode start point Xinit (graph_like_conn.m:6-12; t_dp, feature only).
%       Stored: the values (fast, slow, dp_ll, dp_g), Xinit, the rep counts.
% sf    whole runmodel runs with identity permutations (randperm shim, 'identity'):
%       chain x demo_chain_feat, ring x demo_ring_feat, tree x demo_tree_feat and
%       dirring x demo_ring_rel_bin (reloutsideinit 'overd') at speed 54, and chain x
%       synthtree at speed 5. Spies on structurefit, choose_node_split and graph_like
%       log events: each row is [kind, sfcall, t, nfast, tfast, nslow, tslow] with kind
%       1 = structurefit starts, 2 = a depth starts (the first choose_node_split call
%       of a structurefit call, or the first one whose graph differs from the previous
%       call's: every call of a depth gets the current graph, structurefit.m:28-62),
%       3 = structurefit returns; t is the elapsed time and the counters are the graph_like calls (fast:
%       ps.fast == 1) and the seconds spent in them so far. sf_lls holds each
%       structurefit call's bestgraphlls, sf_ll the run's final score.
% SECTIONS (optional) is a cell array of the sections to run (default {'gl', 'sf'}).
if nargin < 2, sections = {'gl', 'sf'}; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'matlab', 'formdiscovery1.0');
sdir = fullfile(root, 'matlab', 'octave_shims');
fxdir = fullfile(root, 'tests', 'fixtures');
addpath(mdir);
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd
ps0.showtruegraph = 0; ps0.showinferredgraph = 0; ps0.showbestsplit = 0;
ps0.showpreclean = 0; ps0.showpostclean = 0;
out = struct();
more off;
out.octave_version = OCTAVE_VERSION;
out.nproc = nproc();
out.sections = sections;

% --- graph_like / dataprobwsig per call -----------------------------------------------
if any(strcmp(sections, 'gl'))
  FR = load(fullfile(fxdir, 'baseline', 'feat', 'resultsdemo.mat'));
  RR = load(fullfile(fxdir, 'baseline', 'rel', 'resultsdemo.mat'));
  PL = load(fullfile(fxdir, 'paperlevel.mat'));
  specs = {};
  for dind = 1:3
    for sind = [2 4 6]
      specs{end + 1} = {'demo', sind, dind, FR.structure{sind, dind}};
    end
  end
  for q = 1:numel(PL.runs)
    r = PL.runs{q};
    if any(strcmp([r.struct ':' r.data], {'chain:synthchain', 'tree:synthtree', ...
                                           'grid:synthgrid'}))
      specs{end + 1} = {'synth', r.sind, r.dind, r.graph};
    end
  end
  for sd = [17 4; 21 5; 3 6]'
    specs{end + 1} = {'rel', sd(1), sd(2), RR.structure{sd(1), sd(2)}};
  end
  gl = {};
  preps = {};
  for q = 1:numel(specs)
    [grp, sind, dind, g] = specs{q}{:};
    if numel(preps) < dind || isempty(preps{dind})
      [preps{dind}.data, preps{dind}.ps] = prep(ps0, dind);
    end
    data = preps{dind}.data;
    p = preps{dind}.ps;
    p.fixedall = 0; p.fixedinternal = 0; p.fixedexternal = 0; p.prodtied = 0;
    p.runps.structname = ps0.structures{sind};
    r = struct('group', grp, 'structure', ps0.structures{sind}, 'data', ps0.data{dind}, ...
               'sind', sind, 'dind', dind, 'graph', g, 'type', p.runps.type, ...
               'nnodes', size(g.adj, 1), 'fast', [], 't_fast', [], 'n_fast', [], ...
               'slow', [], 't_slow', [], 'n_slow', [], 'Xinit', [], 'dp_ll', [], ...
               'dp_g', [], 't_dp', [], 'n_dp', []);
    pf = p; pf.fast = 1;
    [r.t_fast, r.n_fast, r.fast] = timeit(@() graph_like(data, g, pf), 0.5, 3);
    if ~strcmp(p.runps.type, 'rel')
      ps_ = p; ps_.fast = 0;
      [r.t_slow, r.n_slow, r.slow] = timeit(@() graph_like(data, g, ps_), 1.0, 2);
      % graph_like_conn.m:6-12 (fast mode''s start point) and graph_like.m:7-10
      gL = g;
      gL.Wsym(gL.adjsym > 0) = log(gL.Wsym(gL.adjsym > 0));
      gL.sigma = log(gL.sigma);
      Xinit = [gL.sigma; mat2vec(gL.Wsym, gL, pf)];
      d = data(g.z > 0, :);
      r.Xinit = Xinit;
      [r.t_dp, r.n_dp, r.dp_ll, r.dp_g] = timeit(@() dataprobwsig(Xinit, d, gL, pf), 0.5, 3);
    end
    gl{end + 1} = r;
  end
  out.gl = gl;
end

% --- structurefit per depth -------------------------------------------------------------
if any(strcmp(sections, 'sf'))
  spydir = tempname(); mkdir(spydir);
  rename(mdir, spydir, 'structurefit', 'structurefit(data, ps, graph, savefile)', ...
         'structurefit_orig(data, ps, graph, savefile)', {
    'function [ll, graph, bestgraphlls, bestgraph] = structurefit(data, ps, graph, savefile)'
    'global PERF'
    'PERF.nsf = PERF.nsf + 1; k = PERF.nsf; PERF.have = 0;'
    'perf_event(1, k);'
    '[ll, graph, bestgraphlls, bestgraph] = structurefit_orig(data, ps, graph, savefile);'
    'perf_event(3, k);'
    'PERF.lls{k} = bestgraphlls;'
    'end'});
  rename(mdir, spydir, 'choose_node_split', '=choose_node_split(graph, compind,', ...
         '=choose_node_split_orig(graph, compind,', {
    'function [ll, part1, part2, newgraph] = choose_node_split(graph, compind, splitind, pind, data, ps)'
    'global PERF'
    'if ~PERF.have || ~isequal(graph, PERF.last)'
    '  perf_event(2, PERF.nsf); PERF.last = graph; PERF.have = 1;'
    'end'
    '[ll, part1, part2, newgraph] = choose_node_split_orig(graph, compind, splitind, pind, data, ps);'
    'end'});
  rename(mdir, spydir, 'graph_like', 'function [logI graph] = graph_like(', ...
         'function [logI graph] = graph_like_orig(', {
    'function [logI, graph] = graph_like(data, graph, ps)'
    'global PERF'
    't1 = tic;'
    '[logI, graph] = graph_like_orig(data, graph, ps);'
    'dt = toc(t1);'
    'if isfield(ps, ''fast'') && ps.fast == 1'
    '  PERF.nfast = PERF.nfast + 1; PERF.tfast = PERF.tfast + dt;'
    'else'
    '  PERF.nslow = PERF.nslow + 1; PERF.tslow = PERF.tslow + dt;'
    'end'
    'end'});
  fid = fopen(fullfile(spydir, 'perf_event.m'), 'w');
  fprintf(fid, '%s\n', 'function perf_event(kind, k)', 'global PERF', ...
          ['PERF.ev(end + 1, :) = [kind, k, toc(PERF.t0), PERF.nfast, PERF.tfast, ' ...
           'PERF.nslow, PERF.tslow];'], 'end');
  fclose(fid);
  addpath(sdir, '-begin');     % the randperm shim
  addpath(spydir, '-begin');
  global PERF
  runs = {{'feat', 2, 1, 54}, {'feat', 4, 2, 54}, {'feat', 6, 3, 54}, {'rel', 17, 4, 54}, ...
          {'feat', 2, 10, 5}};
  tmp = tempname(); mkdir(tmp);
  sf = {};
  for q = 1:numel(runs)
    [kind, sind, dind, speed] = runs{q}{:};
    randperm_config('identity');
    PERF = struct('nsf', 0, 'ev', zeros(0, 7), 'nfast', 0, 'tfast', 0, 'nslow', 0, ...
                  'tslow', 0, 'lls', {{}}, 'have', 0, 'last', []);
    PERF.t0 = tic;
    ll = run_one(mdir, fullfile(tmp, sprintf('r%d', q)), kind, sind, dind, speed);
    total = toc(PERF.t0);
    sf{end + 1} = struct('kind', kind, 'structure', ps0.structures{sind}, ...
                         'data', ps0.data{dind}, 'sind', sind, 'dind', dind, ...
                         'speed', speed, 'll', ll, 'total', total, 'ev', PERF.ev, ...
                         'lls', {PERF.lls});
  end
  randperm_config('');
  rmpath(spydir); rmpath(sdir);
  confirm_recursive_rmdir(false, 'local');
  rmdir(spydir, 's'); rmdir(tmp, 's');
  out.sf = sf;
end

save('-v7', outfile, '-struct', 'out');
end

function [t, n, varargout] = timeit(f, mint, minn)
% median seconds per call of F over n calls: at least MINN calls and MINT seconds in
% total, at most 200 calls; varargout = F's outputs on the last call
ts = [];
tot = tic;
while numel(ts) < minn || (toc(tot) < mint && numel(ts) < 200)
  t1 = tic;
  [varargout{1:nargout - 2}] = f();
  ts(end + 1) = toc(t1);
end
t = median(ts);
n = numel(ts);
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

function rename(mdir, spydir, fname, head, newhead, stub)
% <fname>_orig.m = <fname>.m with its header renamed; <fname>.m = STUB (a forwarder)
src = fileread(fullfile(mdir, [fname '.m']));
orig = strrep(src, head, newhead);
if strcmp(orig, src), error('fx_perf: could not rename %s', fname); end
fid = fopen(fullfile(spydir, [fname '_orig.m']), 'w'); fprintf(fid, '%s', orig); fclose(fid);
fid = fopen(fullfile(spydir, [fname '.m']), 'w'); fprintf(fid, '%s\n', stub{:}); fclose(fid);
end

function ll = run_one(mdir, outdir, kind, sind, dind, speed)
% one run as in matlab/run_baseline.m (headless ps, relational runs with reloutsideinit
% 'overd') at ps.speed SPEED; output goes to OUTDIR
olddir = pwd;
cd(mdir); ps = defaultps(setps());   % setps builds ps.dlocs from pwd
ps.showtruegraph = 0; ps.showinferredgraph = 0; ps.showbestsplit = 0;
ps.showpreclean = 0; ps.showpostclean = 0;
ps.speed = speed;
if strcmp(kind, 'rel'), ps.reloutsideinit = 'overd'; end
if ~exist(outdir, 'dir'), mkdir(outdir); end
cd(outdir);
try
  evalc('ll = runmodel(ps, sind, dind, 1);');
catch err
  cd(olddir); rethrow(err);
end
cd(olddir);
end
