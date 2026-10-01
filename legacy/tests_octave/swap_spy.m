function [graph, currscore, overallchange, nearmscores, nearmgraphs] = swap_spy(graph, data, ps, comp, epsilon, currscore, overallchange, loopmax, nearmscores, nearmgraphs, varargin)
% Spy for swapobjclust used by fx_swap.m (item 24). fx_swap writes a swapobjclust.m that
% forwards here; the real function has been copied to swapobjclust_orig.m and the
% subfunctions to swsub.m. Every call runs the original unchanged (the run goes on as
% without the spy) with its randperm draws logged. Some calls are kept:
%   bl  the call itself: the first KEEP per mode (whole/objflag/fastflag/near-miss list)
%       and run, and up to KEEPCH more whose score changed. The call is replayed with the
%       same draws and placeholder strings 'in1', 'in2', ... as near-miss graphs, so the
%       near-miss output shows which entries are new. The replay must give the same
%       graph, score and near-miss scores.
%   pt  for each kept call, the same mode on a worse graph: the input graph with 1-3
%       random object moves and one random swap of the call's own mode applied (doswap +
%       simplify_graph), and loopmax cycling through 1, 2, 3. It runs with seeded draws
%       (rand('state', 1000 + n)), logged; near-miss lists of length 0 or 5.
%   sub the first kept call per mode and run: chooseswaps in every mode (errors
%       caught), sourceobjs, sourcecls, cltypes, and doswap on one random row per mode.
% rand('state') is saved and restored around everything but the real call.
global SPY
KEEP = 2; KEEPCH = 2;
SPY.n = SPY.n + 1;
fid = fopen(SPY.log, 'w'); fclose(fid);
[g2, cs2, oc2, ns2, ng2] = swapobjclust_orig(graph, data, ps, comp, epsilon, currscore, ...
    overallchange, loopmax, nearmscores, nearmgraphs, varargin{:});
logtext = fileread(SPY.log);

objflag = 0; fastflag = 0;
for k = 1:2:numel(varargin)
  switch varargin{k}
    case 'objflag', objflag = varargin{k + 1};
    case 'fastflag', fastflag = varargin{k + 1};
  end
end
mode = sprintf('m%d%d%d%d', isempty(comp), objflag, fastflag, ~isempty(nearmscores));
if ~isfield(SPY.kept, mode), SPY.kept.(mode) = 0; SPY.keptch.(mode) = 0; end
changed = cs2 ~= currscore;
keep = SPY.kept.(mode) < KEEP;
if keep
  SPY.kept.(mode) = SPY.kept.(mode) + 1;
elseif changed && SPY.keptch.(mode) < KEEPCH
  keep = true; SPY.keptch.(mode) = SPY.keptch.(mode) + 1;
end

if keep
  st = rand('state');
  q = struct('speed', ps.speed, 'fast', ps.fast, 'fixedall', ps.fixedall, ...
    'fixedinternal', ps.fixedinternal, 'fixedexternal', ps.fixedexternal, ...
    'prodtied', ps.prodtied, 'cleanstrong', ps.cleanstrong, 'structname', ps.runps.structname);
  if isempty(comp), c = 0; else, c = comp; end
  ph = arrayfun(@(k) sprintf('in%d', k), 1:numel(nearmgraphs), 'UniformOutput', false);
  qf = [SPY.log '.q'];
  fid = fopen(qf, 'w'); fprintf(fid, '%s', logtext); fclose(fid);
  randperm_config(qf, '');
  [g3, cs3, oc3, ns3, ng3] = swapobjclust_orig(graph, data, ps, comp, epsilon, currscore, ...
      overallchange, loopmax, nearmscores, ph, varargin{:});
  randperm_config('', SPY.log);
  if ~isequal(g3, g2) || cs3 ~= cs2 || oc3 ~= oc2 || ~isequal(ns3, ns2)
    error('swap_spy: replay with placeholder near-miss graphs differs');
  end
  r = struct('run', SPY.run, 'n', SPY.n, 'kind', 'bl', 'graph', graph, 'comp', c, ...
    'objflag', objflag, 'fastflag', fastflag, 'epsilon', epsilon, 'currscore', currscore, ...
    'overallchange', overallchange, 'loopmax', loopmax, 'nearmscores', nearmscores, ...
    'ps', q, 'logtext', logtext, 'out_graph', g2, 'out_currscore', cs2, ...
    'out_overallchange', oc2, 'out_nearmscores', ns2);
  r.out_nearmgraphs = ng3;
  SPY.calls{end + 1} = r;

  % pt: a worse graph in the same mode
  rand('state', 1000 + SPY.n);
  tg = graph;
  nmove = 1 + floor(rand() * 3);
  for k = 1:nmove
    [s1, s2] = swsub('chooseswaps', tg, 1, 1, [], 0, 3);
    if size(s1, 1) == 0, break; end
    j = randi_b(size(s1, 1));
    tg = simplify_graph(swsub('doswap', tg, s1(j, :), s2(j, :), 1, ps), ps);
  end
  [s1, s2] = swsub('chooseswaps', tg, isempty(comp), objflag, comp, fastflag, 3);
  if size(s1, 1) > 0 && (isempty(comp) || comp <= tg.ncomp)
    j = randi_b(size(s1, 1));
    tg = simplify_graph(swsub('doswap', tg, s1(j, :), s2(j, :), objflag, ps), ps);
  end
  if isempty(comp) || comp <= tg.ncomp
    [tl, tng] = graph_like(data, tg, ps);
    tscore = tl + graph_prior(tg, ps);
    lm = 1 + mod(SPY.n, 3);
    if mod(SPY.n, 2), nm = -inf * ones(1, 5); else, nm = []; end
    ph = arrayfun(@(k) sprintf('in%d', k), 1:numel(nm), 'UniformOutput', false);
    fid = fopen(SPY.log, 'w'); fclose(fid);
    rand('state', 2000 + SPY.n);
    [g4, cs4, oc4, ns4, ng4] = swapobjclust_orig(tg, data, ps, comp, epsilon, tscore, ...
        0, lm, nm, ph, varargin{:});
    p = r;
    p.kind = 'pt'; p.graph = tg; p.currscore = tscore; p.overallchange = 0;
    p.loopmax = lm; p.nearmscores = nm; p.logtext = fileread(SPY.log);
    p.out_graph = g4; p.out_currscore = cs4; p.out_overallchange = oc4;
    p.out_nearmscores = ns4; p.out_nearmgraphs = ng4;
    SPY.calls{end + 1} = p;
  end

  % sub: the subfunctions on the input graph
  if ~isfield(SPY.subdone, mode)
    SPY.subdone.(mode) = 1;
    s = struct('run', SPY.run, 'n', SPY.n, 'graph', graph, 'ps', q);
    s.sourceobjs = swsub('sourceobjs', graph);
    s.sourcecls = swsub('sourcecls', graph);
    s.sourcecls_i = {}; s.ext = {}; s.int = {};
    for i = 1:graph.ncomp
      s.sourcecls_i{i} = swsub('sourcecls', graph, i);
      [s.ext{i}, s.int{i}] = swsub('cltypes', graph, i);
    end
    % modes: [whole oflag comp fastflag]
    ms = [0 1 0 0; 0 1 0 1; 1 0 0 0; 1 0 0 1];
    for i = 1:graph.ncomp, ms = [ms; 0 0 i 0; 0 0 i 1]; end
    s.cs = {};
    rand('state', 3000 + SPY.n);
    for k = 1:size(ms, 1)
      m = ms(k, :);
      if m(3) == 0, cc = []; else, cc = m(3); end
      t = struct('whole', m(1), 'oflag', m(2), 'comp', m(3), 'fastflag', m(4), 'err', '', ...
                 'sw1', [], 'sw2', [], 'row', 0, 'swapped', []);
      try
        [t.sw1, t.sw2] = swsub('chooseswaps', graph, m(1), m(2), cc, m(4), 3);
        if size(t.sw1, 1) > 0
          t.row = randi_b(size(t.sw1, 1));
          t.swapped = swsub('doswap', graph, t.sw1(t.row, :), t.sw2(t.row, :), m(2), ps);
        end
      catch err
        t.err = err.message;
      end
      s.cs{end + 1} = t;
    end
    SPY.subs{end + 1} = s;
  end
  rand('state', st);
end
graph = g2; currscore = cs2; overallchange = oc2; nearmscores = ns2; nearmgraphs = ng2;
end

function j = randi_b(n)
% not logged: the fixture's own choices
p = builtin('randperm', n);
j = p(1);
end
