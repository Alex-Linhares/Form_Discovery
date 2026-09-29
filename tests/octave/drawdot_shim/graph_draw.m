function [x, y, h] = graph_draw(adj, varargin)
% Shim for graph_draw.m used by fx_viz_dot.m (item 31). draw_dot.m calls graph_draw while
% its temporary files _GtDout.dot and _LAYout.dot still exist in the working directory;
% this shim records their text and the X/Y/node_labels arguments in the global
% DRAWDOT_REC instead of plotting, and returns X and Y as graph_draw does.
global DRAWDOT_REC
x = []; y = []; h = [];
labels = {};
for i = 1:2:numel(varargin)
  switch varargin{i}
    case 'X', x = varargin{i + 1};
    case 'Y', y = varargin{i + 1};
    case 'node_labels', labels = varargin{i + 1};
  end
end
DRAWDOT_REC = struct('gt', fileread('_GtDout.dot'), 'lay', fileread('_LAYout.dot'), ...
                     'X', x, 'Y', y);
DRAWDOT_REC.labels = labels;
