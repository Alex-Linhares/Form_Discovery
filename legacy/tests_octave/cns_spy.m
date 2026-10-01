function [ll, part1, part2, newgraph] = cns_spy(graph, compind, splitind, pind, data, ps)
% choose_node_split wrapper used by fx_structurefit.m (item 27): fx_structurefit writes a
% choose_node_split.m that forwards here and copies the original to
% choose_node_split_orig.m. While GLREC.on is set, every call is recorded in GLREC.cns:
% the arguments (compind, splitind, pind), ll and newgraph (gempty = 1 for []), so that
% Python can tell a tied choice (item 23) from a real difference.
global GLREC
[ll, part1, part2, newgraph] = choose_node_split_orig(graph, compind, splitind, pind, data, ps);
if ~isempty(GLREC) && GLREC.on
  if isempty(newgraph), g = 0; e = 1; else, g = newgraph; e = 0; end
  GLREC.cns{end + 1} = struct('compind', compind, 'splitind', splitind, 'pind', pind, ...
                              'll', ll, 'gempty', e, 'newgraph', g);
end
end
