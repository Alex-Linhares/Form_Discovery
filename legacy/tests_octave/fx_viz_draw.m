function fx_viz_draw(outfile)
% Fixture for item 32 (viz/draw.py, viz/graph_draw.py, viz/pygraphviz_backend.py):
% draw_dot.m l.33-84 (neato call, positions, labels, font size) and graph_draw.m
% (node colours, ellipse radii, edge end points).
%
% graph_draw.m cannot run in Octave as released (ANOMALIES.md): its text calls abbreviate
% 'VerticalAlign' (ambiguous in Octave: verticalalignment / verticalalignmentmode), and its
% subfunction my_arrow reads the MATLAB-only axes properties 'WarpToFill' and 'Xform'. The
% source is left untouched; this script writes a temporary copy of graph_draw.m, first on
% the path, with three textual edits (each count asserted):
%   1. 'VerticalAlign' -> 'VerticalAlignment' (4 times);
%   2. the two my_arrow( calls of the edge loop -> gd_arrow_rec( (legacy/tests_octave/
%      graphdraw_shim/), which records [start stop] of every arrow in drawing order;
%   3. before 'if nargout > 2', a recorder storing x, y, labels, fontsize, nodemult,
%      node_t, color and wd (the ellipse/box half-widths from Octave's text extents) and,
%      when called from draw_dot, the texts of _GtDout.dot and _LAYout.dot.
% Everything else (draw_dot.m, graph_to_dot.m, dot_to_graph.m, the rest of graph_draw.m)
% is the repository's code. The figure is invisible (octave-cli: fltk toolkit).
%
% dd_*  the real draw_dot on: the 74 graphs of fx_viz_dot.m (true graphs and every final
%       baseline graph), labelled as runmodel.m l.35-45/183-188 does (names or '1'..'n',
%       padded with ''); then crafted cases: no labels (nargin 1), singletons, self-loops,
%       'pos', 'nodemult', 'fontsz', an undirected graph, ' ' padding (structurefit's
%       pre/post-clean figures) and a 105-node chain (n > 100: the '-x' branch).
% gd_*  graph_draw called directly: default labels, mixed node_shapes (textbox), a
%       weighted adj (entries ~= 1 are not drawn), vertical and coincident node pairs.
% neato is the fd env's Graphviz 14.1 (put first on PATH, as in fx_viz_dot.m).
global GD_REC GD_ARROWS
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
src = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
setenv('PATH', [fullfile(OCTAVE_HOME(), 'bin') pathsep getenv('PATH')]);
[~, ver] = system('neato -V 2>&1');

tmp = tempname(); mkdir(tmp);
gddir = fullfile(tmp, 'gd'); mkdir(gddir);
txt = fileread(fullfile(src, 'graph_draw.m'));
[txt, c1] = subst(txt, '''VerticalAlign''', '''VerticalAlignment''');
[txt, c2] = subst(txt, 'my_arrow([x(node)+dx1', 'gd_arrow_rec([x(node)+dx1');
rec = ['global GD_REC; GD_REC = struct(''x'', x, ''y'', y, ''fontsize'', fontsize, ' ...
       '''nodemult'', nodemult, ''node_t'', node_t, ''color'', color, ''wd'', wd); ' ...
       'GD_REC.labels = labels; if exist(''_LAYout.dot'', ''file''), ' ...
       'GD_REC.gt = fileread(''_GtDout.dot''); GD_REC.lay = fileread(''_LAYout.dot''); end' ...
       sprintf('\n') 'if nargout > 2'];
[txt, c3] = subst(txt, 'if nargout > 2', rec);
assert(isequal([c1 c2 c3], [4 2 1]), 'graph_draw.m edits: %d %d %d', c1, c2, c3);
fid = fopen(fullfile(gddir, 'graph_draw.m'), 'w'); fwrite(fid, txt); fclose(fid);
addpath(fullfile(here, 'graphdraw_shim'));
addpath(gddir);
assert(strcmp(fileparts(which('graph_draw')), gddir));
old = cd(tmp);
cleanup = onCleanup(@() cd(old));
fig = figure('visible', 'off');

out = struct();
out.neato_version = strtrim(ver);
out.graph_draw_edits = txt;

% --- draw_dot cases -------------------------------------------------------------------
cases = {};
truesets = {'demo_chain_feat', 'demo_ring_feat', 'demo_tree_feat', 'demo_ring_rel_bin', ...
            'demo_hierarchy_rel_bin', 'demo_order_rel_freq', 'synthpartition', ...
            'synthchain', 'synthring', 'synthtree', 'synthgrid'};
for t = truesets
  d = load(fullfile(src, 'data', [t{1} '.mat']));
  if isfield(d, 'names') && ~isempty(d.names)
    nm = d.names;
  else
    if isfield(d, 'objcount'), nobj = d.objcount;
    elseif isfield(d, 'nobj'), nobj = d.nobj;
    elseif isfield(d, 'nobjects'), nobj = d.nobjects;
    else, nobj = size(d.data, 1); end
    nm = {};
    for i = 1:nobj, nm{i} = num2str(i); end
  end
  cases{end + 1} = {['true ' t{1}], full(double(d.adj)), pad(nm, size(d.adj, 1), ''), {}};
end
for kind = {'feat', 'rel'}
  r = load(fullfile(root, 'tests', 'fixtures', 'baseline', kind{1}, 'resultsdemo.mat'));
  for dind = 1:size(r.structure, 2)
    for sind = 1:size(r.structure, 1)
      g = r.structure{sind, dind, 1};
      if ~isstruct(g), continue; end
      cases{end + 1} = {sprintf('%s %d %d', kind{1}, sind, dind), full(double(g.adj)), ...
                        pad(r.names{dind}, size(g.adj, 1), ''), {}};
    end
  end
end
a6 = zeros(6); a6(1, 3) = 1; a6(3, 4) = 1; a6(4, 6) = 1; a6(6, 1) = 1;   % 2, 5 isolated
al = zeros(5); al(1, 1) = 1; al(1, 2) = 1; al(2, 3) = 1; al(4, 4) = 1; al(3, 5) = 1;
au = [0 1 1 0 0; 1 0 0 1 0; 1 0 0 0 1; 0 1 0 0 1; 0 0 1 1 0];            % undirected
ch = diag(ones(1, 104), 1); ch = ch + ch';                                % 105 nodes
xo = [0.1 0.3 0.5 0.7 0.9; 0.2 0.9 0.1 0.6 0.4];
cases{end + 1} = {'nolabels', a6, [], {}};
cases{end + 1} = {'singletons', a6, {'a', 'b', 'c', 'd', 'e', 'f'}, {}};
cases{end + 1} = {'selfloops', al, {'L1', 'x', 'y', 'L4', 'z'}, {}};
cases{end + 1} = {'pos', au, {'p', 'q', 'r', 's', 't'}, {'pos', xo}};
cases{end + 1} = {'nodemult', au, {'p', 'q', 'r', 's', 't'}, {'nodemult', 0.08}};
cases{end + 1} = {'fontsz', al, {'L1', 'x', 'y', 'L4', 'z'}, {'fontsz', 15, 'nodemult', 0.9}};
cases{end + 1} = {'undirected', au, {'p', 'q', 'r', 's', 't'}, {}};
cases{end + 1} = {'spacepad', a6, pad({'o1', 'o2', 'o3'}, 6, ' '), {}};
cases{end + 1} = {'chain105', ch, pad({}, 105, ''), {}};
fld = {'dd_run', 'dd_adj', 'dd_labels_in', 'dd_args', 'dd_gt', 'dd_lay', 'dd_xret', ...
       'dd_yret', 'dd_labels_out', 'dd_x', 'dd_y', 'dd_labels', 'dd_fontsize', ...
       'dd_nodemult', 'dd_color', 'dd_wd', 'dd_arrows'};
for f = fld, out.(f{1}) = {}; end
for k = 1:numel(cases)
  c = cases{k};
  GD_REC = []; GD_ARROWS = zeros(0, 4);
  clf(fig);
  if isempty(c{3}) && ~iscell(c{3})
    [xr, yr, lo] = draw_dot(c{2});
  else
    [xr, yr, lo] = draw_dot(c{2}, c{3}, c{4}{:});
  end
  assert(~exist('_GtDout.dot', 'file') && ~exist('_LAYout.dot', 'file'));
  out.dd_run{end + 1} = c{1}; out.dd_adj{end + 1} = c{2};
  out.dd_labels_in{end + 1} = c{3}; out.dd_args{end + 1} = c{4};
  out.dd_gt{end + 1} = GD_REC.gt; out.dd_lay{end + 1} = GD_REC.lay;
  out.dd_xret{end + 1} = xr; out.dd_yret{end + 1} = yr; out.dd_labels_out{end + 1} = lo;
  out.dd_x{end + 1} = GD_REC.x; out.dd_y{end + 1} = GD_REC.y;
  out.dd_labels{end + 1} = GD_REC.labels; out.dd_fontsize{end + 1} = GD_REC.fontsize;
  out.dd_nodemult{end + 1} = GD_REC.nodemult; out.dd_color{end + 1} = GD_REC.color;
  out.dd_wd{end + 1} = GD_REC.wd; out.dd_arrows{end + 1} = GD_ARROWS;
end

% --- graph_draw called directly --------------------------------------------------------
g1 = [0 1 0 0; 0 0 1 0; 0 0 1 1; 1 0 0 0];
g2 = [0 2 1 0; 0 0 1 0; 0 0 0 1; 1 0 0 0];
gcases = {
  {'default', g1, {'X', [0.1 0.4 0.6 0.9], 'Y', [0.5 0.2 0.8 0.3]}}
  {'shapes', g1, {'node_labels', {'aa', 'b', 'cccc', 'd'}, 'node_shapes', [0 1 0 1], ...
                  'X', [0.1 0.4 0.6 0.9], 'Y', [0.5 0.2 0.8 0.3]}}
  {'weighted', g2, {'node_labels', {'a', 'b', 'c', 'd'}, 'fontsize', 10, ...
                    'X', [0.1 0.4 0.6 0.9], 'Y', [0.5 0.2 0.8 0.3]}}
  {'vertical', g1 + g1', {'node_labels', {'a', 'b', 'c', 'd'}, ...
                          'X', [0.3 0.3 0.7 0.3], 'Y', [0.2 0.8 0.5 0.5]}}
  {'coincident', [0 1 0; 0 0 1; 0 0 0], {'node_labels', {'a', 'b', 'c'}, ...
                                         'X', [0.5 0.5 0.2], 'Y', [0.5 0.5 0.9]}}
};
fld = {'gd_run', 'gd_adj', 'gd_args', 'gd_x', 'gd_y', 'gd_labels', 'gd_fontsize', ...
       'gd_nodemult', 'gd_node_t', 'gd_color', 'gd_wd', 'gd_arrows'};
for f = fld, out.(f{1}) = {}; end
for k = 1:numel(gcases)
  c = gcases{k};
  GD_REC = []; GD_ARROWS = zeros(0, 4);
  clf(fig);
  graph_draw(c{2}, c{3}{:});
  out.gd_run{end + 1} = c{1}; out.gd_adj{end + 1} = c{2}; out.gd_args{end + 1} = c{3};
  out.gd_x{end + 1} = GD_REC.x; out.gd_y{end + 1} = GD_REC.y;
  out.gd_labels{end + 1} = GD_REC.labels; out.gd_fontsize{end + 1} = GD_REC.fontsize;
  out.gd_nodemult{end + 1} = GD_REC.nodemult; out.gd_node_t{end + 1} = GD_REC.node_t;
  out.gd_color{end + 1} = GD_REC.color; out.gd_wd{end + 1} = GD_REC.wd;
  out.gd_arrows{end + 1} = GD_ARROWS;
end

close(fig);
cd(old);
rmpath(gddir); rmpath(fullfile(here, 'graphdraw_shim'));
confirm_recursive_rmdir(false, 'local');
rmdir(tmp, 's');
save('-v7', outfile, '-struct', 'out');
end

function [s, n] = subst(s, a, b)
n = numel(strfind(s, a));
s = strrep(s, a, b);
end

function c = pad(c, n, fill)
% runmodel.m l.42-44 / 184-186, structurefit.m l.89-91: names{i} = fill for the
% cluster nodes
for i = numel(c) + 1:n
  c{i} = fill;
end
end
