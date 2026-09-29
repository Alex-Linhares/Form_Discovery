function gd_arrow_rec(start, stop)
% Shim for fx_viz_draw.m (item 32). graph_draw.m's edge loop calls its subfunction
% my_arrow(start, stop), which cannot run in Octave (it reads the MATLAB-only axes
% properties 'WarpToFill' and 'Xform'). fx_viz_draw.m runs a temporary copy of graph_draw.m
% in which both calls are renamed to gd_arrow_rec; this records [start stop] (one row per
% arrow, in drawing order) in the global GD_ARROWS and draws a plain line instead.
global GD_ARROWS
GD_ARROWS(end + 1, :) = [start(:)' stop(:)'];
line([start(1) stop(1)], [start(2) stop(2)]);
