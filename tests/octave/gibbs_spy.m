function [ll, graph] = gibbs_spy(varargin)
% Spy for gibbs_clean used by fx_gibbs.m (item 26). fx_gibbs writes a gibbs_clean.m that
% forwards here; the real function is gibbs_clean_orig.m, and graph_like.m is replaced by
% a wrapper (glc_spy.m) that records every slow call (ps.fast == 0) while GLREC.on is set.
% Every call runs the original unchanged (the run goes on as without the spy), with its
% randperm draws logged and its slow graph_like calls recorded. Some calls are kept:
%   bl  the call itself: the first KEEP per mode (speed, options) and run, and up to
%       KEEPCH more that changed the graph.
%   pt  for each kept call, the same call on a worse graph: 1-3 random object moves
%       (swsub chooseswaps/doswap, full mode, whole graph), each followed by
%       simplify_graph, with seeded (logged) draws (rand('state', 2000 + n)).
%   g0  for the first kept speed-4 call per run, the call with ps.gibbsclean = 0.
% rand('state') is saved and restored around everything but the real call.
global SPY GLREC
KEEP = 2; KEEPCH = 2;
SPY.n = SPY.n + 1;
a = varargin;
graph = a{1}; data = a{2}; ps = a{3};
opt = struct('loopmax', 1, 'nearmisses', 0, 'loopeps', 1e-4, 'swaptypes', [1 1 1 1 1], ...
             'fast', 0);
for k = 4:2:numel(a)
  opt.(a{k}) = a{k + 1};
end
[ll2, g2, logtext, gl] = run_orig(a);

mode = sprintf('s%d_f%d_nm%d_lm%d_sw%s', ps.speed, opt.fast, opt.nearmisses, opt.loopmax, ...
               sprintf('%d', opt.swaptypes));
if ~isfield(SPY.kept, mode), SPY.kept.(mode) = 0; SPY.keptch.(mode) = 0; end
changed = ~isequal(g2.z, graph.z) || ~isequal(size(g2.adj), size(graph.adj));
keep = SPY.kept.(mode) < KEEP;
if keep
  SPY.kept.(mode) = SPY.kept.(mode) + 1;
elseif changed && SPY.keptch.(mode) < KEEPCH
  keep = true; SPY.keptch.(mode) = SPY.keptch.(mode) + 1;
end

if keep
  st = rand('state');
  r = struct('run', SPY.run, 'n', SPY.n, 'kind', 'bl', 'graph', graph, 'opt', opt, ...
    'ps', psq(ps), 'logtext', logtext, 'out_ll', ll2, 'out_graph', g2);
  r.gl = gl;
  SPY.calls{end + 1} = r;

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
  b = a; b{1} = tg;
  rand('state', 2000 + SPY.n);
  [ll4, g4, logtext4, gl4] = run_orig(b);
  p = r;
  p.kind = 'pt'; p.graph = tg; p.logtext = logtext4; p.out_ll = ll4; p.out_graph = g4;
  p.gl = gl4;
  SPY.calls{end + 1} = p;

  % g0: ps.gibbsclean = 0 at speed 4
  if ps.speed < 5 && ~isfield(SPY, 'g0done')
    SPY.g0done = 1;
    b = a; b{3}.gibbsclean = 0;
    rand('state', 3000 + SPY.n);
    [ll5, g5, logtext5, gl5] = run_orig(b);
    p = r;
    p.kind = 'g0'; p.ps = psq(b{3}); p.logtext = logtext5; p.out_ll = ll5; p.out_graph = g5;
    p.gl = gl5;
    SPY.calls{end + 1} = p;
  end
  rand('state', st);
end
ll = ll2; graph = g2;
end

function [ll, g, logtext, gl] = run_orig(a)
global SPY GLREC
fid = fopen(SPY.log, 'w'); fclose(fid);
GLREC = struct('on', 1, 'list', {{}});
[ll, g] = gibbs_clean_orig(a{:});
gl = GLREC.list;
GLREC.on = 0;
logtext = fileread(SPY.log);
end

function q = psq(ps)
% fast is NaN when ps has no field fast (set only by gibbs_clean and graph_like callers)
if isfield(ps, 'fast'), fast = ps.fast; else, fast = NaN; end
q = struct('speed', ps.speed, 'fast', fast, 'gibbsclean', ps.gibbsclean, ...
  'nauty', ps.nauty, 'fixedall', ps.fixedall, 'fixedinternal', ps.fixedinternal, ...
  'fixedexternal', ps.fixedexternal, 'prodtied', ps.prodtied, ...
  'cleanstrong', ps.cleanstrong, 'structname', ps.runps.structname);
end

function j = randi_b(n)
% not logged: the fixture's own choices
p = builtin('randperm', n);
j = p(1);
end
