function [logI, graph] = glc_spy(data, graph, ps)
% graph_like wrapper used by fx_gibbs.m (item 26): fx_gibbs writes a graph_like.m that
% forwards here and copies the original to graph_like_orig.m. While GLREC.on is set,
% every slow call (ps.fast == 0) is recorded: input graph, logI and output graph.
global GLREC
if ~isempty(GLREC) && GLREC.on && ps.fast == 0
  g0 = graph;
  [logI, graph] = graph_like_orig(data, graph, ps);
  GLREC.list{end + 1} = struct('graph', g0, 'logI', logI, 'out_graph', graph);
else
  [logI, graph] = graph_like_orig(data, graph, ps);
end
end
