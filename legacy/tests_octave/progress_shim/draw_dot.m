function [x, y, labels] = draw_dot(adj, labels, varargin)
% Shim for fx_viz_progress.m (item 32). With every ps.show* flag set, runmodel.m,
% structurefit.m and best_split.m call figure(n), clf, title(...), draw_dot(adj, names)
% and drawnow. This directory shadows all five; each appends {name, args...} to the
% global PROGRESS_LOG, so the fixture holds the exact sequence of display calls (the
% graphs, the padded names and the formatted titles) without drawing anything.
global PROGRESS_LOG
PROGRESS_LOG{end + 1} = {'draw_dot', full(double(adj)), labels};
x = []; y = [];
