function [graph, currscore, overallchange, nearmscores, nearmgraphs] = l4b2_spy(fn, varargin)
% Spy for spr and collapsedims used by fx_spr.m (item 25). fx_spr writes an spr.m and a
% collapsedims.m that forward here; the real functions have been copied to spr_orig.m and
% collapsedims_orig.m and their subfunctions to sprsub.m and cdsub.m. Every call runs the
% original unchanged (the run goes on as without the spy) with its randperm draws logged.
% Some calls are kept:
%   bl  the call itself: the first KEEP per mode (function, component, near-miss list)
%       and run, and up to KEEPCH more whose score changed. The call is replayed with the
%       same draws and placeholder strings 'in1', 'in2', ... as near-miss graphs, so the
%       near-miss output shows which entries are new. The replay must agree.
%   pt  for each kept call, the same call on a worse graph: 1-3 random object moves
%       (swsub chooseswaps/doswap, full mode, whole graph) and, for spr, one random regraft
%       (sprsub makers + subtreeattach), each followed by simplify_graph. Seeded draws
%       (rand('state', 2000 + n)), logged; near-miss lists of length 0 or 5; collapsedims
%       loopmax cycles through 1, 2, 3.
%   sub the first kept call per mode and run: spr's makers for every node (objflag 0) and
%       every object (objflag 1), errors caught; collapsedims' get_occnodescomp and getocc
%       for every component and node, and zassign on one random (occupied, vacant) pair.
% rand('state') is saved and restored around everything but the real call.
global SPY
KEEP = 2; KEEPCH = 2;
SPY.n = SPY.n + 1;
a = varargin;
isspr = strcmp(fn, 'spr');
if isspr
  % spr(graph, data, ps, i, epsilon, currscore, overallchange, debug, nearmscores, nearmgraphs)
  inm = 9; comp = a{4}; loopmax = 0;
else
  % collapsedims(graph, data, ps, epsilon, currscore, overallchange, loopmax, nearmscores, nearmgraphs)
  inm = 8; comp = 0; loopmax = a{7};
end
graph = a{1}; data = a{2}; ps = a{3};
if isspr, epsilon = a{5}; cs0 = a{6}; oc0 = a{7}; else, epsilon = a{4}; cs0 = a{5}; oc0 = a{6}; end
fid = fopen(SPY.log, 'w'); fclose(fid);
[g2, cs2, oc2, ns2, ng2] = feval([fn '_orig'], a{:});
logtext = fileread(SPY.log);

mode = sprintf('%s_c%d_nm%d', fn, comp, ~isempty(a{inm}));
if ~isfield(SPY.kept, mode), SPY.kept.(mode) = 0; SPY.keptch.(mode) = 0; end
changed = cs2 ~= cs0;
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
  ph = arrayfun(@(k) sprintf('in%d', k), 1:numel(a{inm + 1}), 'UniformOutput', false);
  qf = [SPY.log '.q'];
  fid = fopen(qf, 'w'); fprintf(fid, '%s', logtext); fclose(fid);
  randperm_config(qf, '');
  b = a; b{inm + 1} = ph;
  [g3, cs3, oc3, ns3, ng3] = feval([fn '_orig'], b{:});
  randperm_config('', SPY.log);
  if ~isequal(g3, g2) || cs3 ~= cs2 || oc3 ~= oc2 || ~isequal(ns3, ns2)
    error('l4b2_spy: replay with placeholder near-miss graphs differs');
  end
  r = struct('fn', fn, 'run', SPY.run, 'n', SPY.n, 'kind', 'bl', 'graph', graph, ...
    'comp', comp, 'epsilon', epsilon, 'currscore', cs0, 'overallchange', oc0, ...
    'loopmax', loopmax, 'nearmscores', a{inm}, 'ps', q, 'logtext', logtext, ...
    'out_graph', g2, 'out_currscore', cs2, 'out_overallchange', oc2, 'out_nearmscores', ns2);
  r.out_nearmgraphs = ng3;
  SPY.calls{end + 1} = r;
  if ~isspr   % context for fx_spr's crafted calls
    SPY.ctx = struct('ps', ps, 'data', data, 'graph', graph, 'q', q, 'run', SPY.run);
  end

  % pt: a worse graph
  rand('state', 1000 + SPY.n);
  tg = graph;
  nmove = 1 + floor(rand() * 3);
  for k = 1:nmove
    [s1, s2] = swsub('chooseswaps', tg, 1, 1, [], 0, 3);
    if size(s1, 1) == 0, break; end
    j = randi_b(size(s1, 1));
    tg = simplify_graph(swsub('doswap', tg, s1(j, :), s2(j, :), 1, ps), ps);
  end
  if isspr && comp <= tg.ncomp && tg.components{comp}.nodecount > 1
    if strcmp(tg.components{comp}.type, 'tree'), of = floor(rand() * 2); else, of = 0; end
    if of, nj = tg.objcount; else, nj = tg.components{comp}.nodecount; end
    for t = 1:10          % a node that can be regrafted
      j = randi_b(nj);
      [rs, cs] = sprsub('makers', tg, j, comp, of);
      if ~isempty(rs)
        e = randi_b(numel(rs));
        tg = simplify_graph(subtreeattach(tg, j, rs(e), cs(e), comp, ps, 'objflag', of), ps);
        break;
      end
    end
  end
  if ~isspr || (comp <= tg.ncomp && tg.components{comp}.nodecount > 1)
    [tl, tng] = graph_like(data, tg, ps);
    tscore = tl + graph_prior(tg, ps);
    if mod(SPY.n, 2), nm = -inf * ones(1, 5); else, nm = []; end
    ph = arrayfun(@(k) sprintf('in%d', k), 1:numel(nm), 'UniformOutput', false);
    b = a; b{1} = tg; b{inm} = nm; b{inm + 1} = ph;
    if isspr, b{6} = tscore; b{7} = 0; else, b{5} = tscore; b{6} = 0; b{7} = 1 + mod(SPY.n, 3); end
    fid = fopen(SPY.log, 'w'); fclose(fid);
    rand('state', 2000 + SPY.n);
    [g4, cs4, oc4, ns4, ng4] = feval([fn '_orig'], b{:});
    p = r;
    p.kind = 'pt'; p.graph = tg; p.currscore = tscore; p.overallchange = 0;
    if ~isspr, p.loopmax = b{7}; end
    p.nearmscores = nm; p.logtext = fileread(SPY.log);
    p.out_graph = g4; p.out_currscore = cs4; p.out_overallchange = oc4;
    p.out_nearmscores = ns4; p.out_nearmgraphs = ng4;
    SPY.calls{end + 1} = p;
  end

  % sub: the subfunctions on the input graph
  if ~isfield(SPY.subdone, mode)
    SPY.subdone.(mode) = 1;
    s = struct('fn', fn, 'run', SPY.run, 'n', SPY.n, 'graph', graph, 'ps', q, 'comp', comp);
    if isspr
      s.mk = {};
      for of = 0:1
        if of, nj = graph.objcount; else, nj = graph.components{comp}.nodecount; end
        for j = 1:nj
          t = struct('objflag', of, 'j', j, 'rs', [], 'cs', [], 'err', '');
          try
            [t.rs, t.cs] = sprsub('makers', graph, j, comp, of);
          catch err
            t.err = err.message;
          end
          s.mk{end + 1} = t;
        end
      end
    else
      s.occn = {}; s.go = {};
      for i = 1:graph.ncomp
        s.occn{i} = cdsub('get_occnodescomp', graph, i);
        for j = 1:graph.compsizes(i)
          t = struct('i', i, 'j', j);
          [t.occ, t.unocc] = cdsub('getocc', graph, i, j);
          s.go{end + 1} = t;
        end
      end
      rand('state', 3000 + SPY.n);
      occ = unique(graph.z);
      unocc = setdiff(1:size(graph.Wcluster, 1), occ);
      s.za_from = occ(randi_b(numel(occ)));
      if isempty(unocc), s.za_to = occ(1); else, s.za_to = unocc(randi_b(numel(unocc))); end
      s.za = cdsub('zassign', s.za_from, s.za_to, graph, 1, 1);
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
