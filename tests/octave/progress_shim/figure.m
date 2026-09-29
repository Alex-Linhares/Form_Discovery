function h = figure(varargin)
% Shim for fx_viz_progress.m (item 32): records figure(n) in the global PROGRESS_LOG
% instead of opening a window. See draw_dot.m in this directory.
global PROGRESS_LOG
PROGRESS_LOG{end + 1} = {'figure', varargin{:}};
h = 1;
