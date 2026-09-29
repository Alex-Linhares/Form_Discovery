function drawnow(varargin)
% Shim for fx_viz_progress.m (item 32): records drawnow in the global PROGRESS_LOG.
global PROGRESS_LOG
PROGRESS_LOG{end + 1} = {'drawnow'};
