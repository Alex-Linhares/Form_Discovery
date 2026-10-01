function h = title(str, varargin)
% Shim for fx_viz_progress.m (item 32): records the title text in the global PROGRESS_LOG.
global PROGRESS_LOG
PROGRESS_LOG{end + 1} = {'title', str};
h = 1;
