function [ll, graph, bestgraphlls, bestgraph] = sf_spy(data, ps, graph, savefile)
% Spy for structurefit used by fx_structurefit.m (item 27). fx_structurefit writes a
% structurefit.m that forwards here; the real function is structurefit_orig.m, and
% graph_like.m is replaced by glc_spy.m, which records every slow call (ps.fast == 0)
% while GLREC.on is set. Every call runs the original unchanged (the run goes on as
% without the spy) and is kept: the input graph ([] -> gempty = 1), the ps fields that
% vary, the randperm draws (logtext), the slow graph_like calls (gl, in call order), the
% choose_node_split calls (cns, recorded by cns_spy.m), the
% outputs, and the bestgraphlls saved to SAVEFILE (saved_lls; NaN when nothing was saved).
% kind is SPY.kind ('bl' when unset: a real call). The first real call on a product
% graph leaves its context (data, ps, output graph) in SPY.ctx.
global SPY GLREC
SPY.n = SPY.n + 1;
g0 = graph;
% Octave's save does not append .mat to SAVEFILE (MATLAB does): look for both names
sf = {savefile, [savefile '.mat']};
for k = 1:2, if exist(sf{k}, 'file'), delete(sf{k}); end, end
fid = fopen(SPY.log, 'w'); fclose(fid);
GLREC = struct('on', 1, 'list', {{}}, 'cns', {{}});
[ll, graph, bestgraphlls, bestgraph] = structurefit_orig(data, ps, g0, savefile);
gl = GLREC.list;
cns = GLREC.cns;
GLREC.on = 0;
logtext = fileread(SPY.log);
saved_lls = NaN;
for k = 1:2
  if exist(sf{k}, 'file'), s = load(sf{k}); saved_lls = s.bestgraphlls; end
end
if isempty(g0), gempty = 1; g0 = struct('ncomp', 0); else, gempty = 0; end
if isfield(SPY, 'kind'), kind = SPY.kind; else, kind = 'bl'; end
r = struct('run', SPY.run, 'n', SPY.n, 'kind', kind, 'gempty', gempty, 'graph', g0, 'ps', psq(ps), ...
           'logtext', logtext, 'out_ll', ll, 'out_graph', graph, ...
           'out_lls', bestgraphlls, 'saved_lls', saved_lls);
r.out_bestgraph = bestgraph;
r.gl = gl;
r.cns = cns;
SPY.calls{end + 1} = r;
% context for fx_structurefit's crafted calls: the first product-graph call
if g0.ncomp > 1 && ~isfield(SPY, 'ctx') && ~isfield(SPY, 'kind')
  SPY.ctx = struct('data', data, 'ps', ps, 'graph', graph, 'savefile', savefile);
end
end

function q = psq(ps)
if isfield(ps, 'fast'), fast = ps.fast; else, fast = NaN; end
q = struct('speed', ps.speed, 'fast', fast, 'gibbsclean', ps.gibbsclean, ...
  'nauty', ps.nauty, 'fixedall', ps.fixedall, 'fixedinternal', ps.fixedinternal, ...
  'fixedexternal', ps.fixedexternal, 'prodtied', ps.prodtied, ...
  'cleanstrong', ps.cleanstrong, 'init', ps.init, 'structname', ps.runps.structname);
end
