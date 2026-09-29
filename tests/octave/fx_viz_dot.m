function fx_viz_dot(outfile)
% Fixture for item 31 (viz/dot.py): graph_to_dot.m and dot_to_graph.m (patched, see
% matlab/PATCHES.md).
%
% bl_*  the true graph (adj) of the 11 data sets that store one, then every final graph
%       of the committed baselines (9 feature + 54 relational runs, resultsdemo.mat), 74
%       in all. The unmodified draw_dot(adj, names) runs in a temporary
%       directory, with the graph_draw shim in tests/octave/drawdot_shim/ recording the text
%       of _GtDout.dot (graph_to_dot) and _LAYout.dot (neato -Tdot layout) and the X/Y
%       draw_dot passes on. dot_to_graph is then called on a copy of the layout file.
%       Saved: bl_run ('true <data>' or 'feat'/'rel' sind dind), bl_adj, bl_gt, bl_lay, bl_A, bl_labels,
%       bl_x, bl_y (dot_to_graph), bl_xret, bl_yret (draw_dot outputs), bl_X, bl_Y.
% go_*  graph_to_dot option variants (node_label, arc_label, width/height incl. a
%       non-integer width, leftright, directed 0/1) on small graphs; go_err holds the
%       error message ('' if none) of the undirected + arc_label case (typo labeltext).
% cr_*  dot_to_graph on crafted DOT texts (chained edges, mixed -- and ->, no coordinates,
%       non-square adjacency, substring labels in both orders, zero coordinates, ...).
%       cr_err holds the error message ('' if none), cr_warn the last warning message.
% neato is taken from the Octave prefix's bin/ (the fd env, Graphviz 14.1), put first on
% PATH so the broken system /usr/bin/neato is not used (matlab/PATCHES.md).
global DRAWDOT_REC
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
addpath(fullfile(here, 'drawdot_shim'));
setenv('PATH', [fullfile(OCTAVE_HOME(), 'bin') pathsep getenv('PATH')]);
[~, ver] = system('neato -V 2>&1');
tmp = tempname(); mkdir(tmp); old = cd(tmp);
cleanup = onCleanup(@() cd(old));

out = struct();
out.neato_version = strtrim(ver);
out.bl_run = {}; out.bl_adj = {}; out.bl_gt = {}; out.bl_lay = {};
out.bl_A = {}; out.bl_labels = {}; out.bl_x = {}; out.bl_y = {};
out.bl_xret = {}; out.bl_yret = {}; out.bl_X = {}; out.bl_Y = {};
% the true graphs of the data sets that store one (runmodel.m:45 draws them when
% ps.showtruegraph is set); unlike graph.adj most of these are symmetric
truesets = {'demo_chain_feat', 'demo_ring_feat', 'demo_tree_feat', 'demo_ring_rel_bin', ...
            'demo_hierarchy_rel_bin', 'demo_order_rel_freq', 'synthpartition', ...
            'synthchain', 'synthring', 'synthtree', 'synthgrid'};
runs = {};
for t = truesets
  d = load(fullfile(root, 'matlab', 'formdiscovery1.0', 'data', [t{1} '.mat']), 'adj');
  runs{end + 1} = {['true ' t{1}], full(double(d.adj)), {}};
end
for kind = {'feat', 'rel'}
  r = load(fullfile(root, 'tests', 'fixtures', 'baseline', kind{1}, 'resultsdemo.mat'));
  for dind = 1:size(r.structure, 2)
    for sind = 1:size(r.structure, 1)
      g = r.structure{sind, dind, 1};
      if ~isstruct(g), continue; end
      runs{end + 1} = {sprintf('%s %d %d', kind{1}, sind, dind), full(double(g.adj)), ...
                       r.names{dind}};
    end
  end
end
for k = 1:numel(runs)
  DRAWDOT_REC = [];
  [xr, yr] = draw_dot(runs{k}{2}, runs{k}{3});
  assert(~exist('_GtDout.dot', 'file') && ~exist('_LAYout.dot', 'file'));
  fid = fopen('lay.dot', 'w'); fwrite(fid, DRAWDOT_REC.lay); fclose(fid);
  [A, l, x, y] = dot_to_graph('lay.dot');
  out.bl_run{end + 1} = runs{k}{1};
  out.bl_adj{end + 1} = runs{k}{2};
  out.bl_gt{end + 1} = DRAWDOT_REC.gt;
  out.bl_lay{end + 1} = DRAWDOT_REC.lay;
  out.bl_A{end + 1} = A;
  out.bl_labels{end + 1} = l;
  out.bl_x{end + 1} = x; out.bl_y{end + 1} = y;
  out.bl_xret{end + 1} = xr; out.bl_yret{end + 1} = yr;
  out.bl_X{end + 1} = DRAWDOT_REC.X; out.bl_Y{end + 1} = DRAWDOT_REC.Y;
end

% --- graph_to_dot option variants ---------------------------------------------------
a1 = [0 1 1 0; 0 0 0 1; 0 0 0 0; 0 0 1 0];          % directed
a2 = [0 1 0 1; 1 0 1 0; 0 1 1 1; 1 0 1 0];          % undirected, self-loop on 3
a3 = zeros(3);                                      % no edges
nl = {'alpha', 'b c', 'x"y', ''};
al = cell(4); al{1, 2} = 'w12'; al{1, 3} = 'w13'; al{2, 4} = ''; al{4, 3} = 'w43';
cases = {
  {a1, {}}
  {a1, {'directed', 0}}
  {a2, {'directed', 0}}
  {a2, {'directed', 1}}
  {a1, {'node_label', nl}}
  {a1, {'arc_label', al}}
  {a1, {'arc_label', al, 'node_label', nl, 'leftright', 1}}
  {a1, {'width', 7, 'height', 3}}
  {a1, {'width', 10.5, 'height', 1/3}}
  {a1, {'leftright', 1, 'directed', 0}}
  {a2, {'directed', 0, 'arc_label', al}}
  {a3, {}}
  {a3, {'directed', 0}}
  {2 * a1, {'directed', 1}}
  {a2, {'directed', 0, 'node_label', nl, 'width', 5}}
};
out.go_adj = {}; out.go_args = {}; out.go_text = {}; out.go_err = {};
for k = 1:numel(cases)
  c = cases{k};
  if exist('go.dot', 'file'), delete('go.dot'); end
  err = '';
  try
    graph_to_dot(c{1}, c{2}{:}, 'filename', 'go.dot');
  catch e
    err = e.message;
    fclose('all');
  end
  if exist('go.dot', 'file'), txt = fileread('go.dot'); else, txt = ''; end
  out.go_adj{end + 1} = c{1}; out.go_args{end + 1} = c{2};
  out.go_text{end + 1} = txt; out.go_err{end + 1} = err;
end

% --- dot_to_graph on crafted texts ----------------------------------------------------
nl = sprintf('\n');
texts = {
  ['graph G {' nl 'a -- b -- c;' nl 'c -- a;' nl '}']
  ['digraph G {' nl '1 -> 2 -> 3 [pos="e,1,1 2,2"];' nl '3 -- 1;' nl '2 -> 2;' nl '}']
  ['digraph G {' nl '1 -> 2;' nl '1 -> 3;' nl '}']
  ['digraph G {' nl '3 -> 1;' nl '3 -> 2;' nl '2 [pos="5,7"];' nl '1 [pos="1,2"];' nl '3 [pos="9,4.5"];' nl '}']
  ['graph G {' nl '10 -- 1;' nl '1 -- 11;' nl '1 [pos="1,1"];' nl '10 [pos="2,3"];' nl '11 [pos="4,9"];' nl '}']
  ['graph G {' nl '1 -- 10;' nl '11 -- 1;' nl '10 [pos="2,3"];' nl '1 [pos="1,1"];' nl '11 [pos="4,9"];' nl '}']
  ['graph G {' nl '1 -- 2;' nl '1 [pos="0,0"];' nl '2 [pos="30,0"];' nl '}']
  ['graph G {' nl '1 -- 2;' nl '1 [pos="-3.5e1,2"];' nl '2 [pos="+30.25,1E1"];' nl '}']
  ['  graph G {' nl nl '   x   --  y  ;  ' nl sprintf('\t') 'x [ label="x", pos = "3,4" ];' nl 'y [label="y",' nl ' width=1, pos="5,6"];' nl '}' nl]
  ['graph G {' nl '1 -- 2;' nl '2 -- 1;' nl '1 [pos="1,1"];' nl '2 [pos="2,5"];' nl '}']
  ['G {' nl '1 -- 2;' nl '}']
  ['graph G {' nl '1 [pos="1,1"];' nl '}']
  ['graph G {' nl '1 -- 2;' nl '1 [pos="7"];' nl '}']
  ['graph G {' nl '/* 1 -- 5; */ 1 -- 2; /* multi' nl 'line 3 -- 4 */' nl '1 [pos="1,1"]; 2 [pos="2,2"];' nl '}']
  ['digraph G {' nl 'a -> b -- c [x];' nl 'c [pos="1,2"];' nl 'b [pos="3,5"];' nl '}']
  ['digraph G {' sprintf('\r\n') 'ab -> cd;' sprintf('\r\n') 'ab [pos="1,2"];' sprintf('\r\n') 'cd [pos="3,2"];' sprintf('\r\n') '}']
};
out.cr_text = texts';
out.cr_A = {}; out.cr_labels = {}; out.cr_x = {}; out.cr_y = {}; out.cr_err = {}; out.cr_warn = {};
for k = 1:numel(texts)
  fid = fopen('cr.dot', 'w'); fwrite(fid, texts{k}); fclose(fid);
  lastwarn('');
  err = ''; A = []; l = {}; x = []; y = [];
  try
    [A, l, x, y] = dot_to_graph('cr.dot');
  catch e
    err = e.message;
  end
  out.cr_A{end + 1} = A; out.cr_labels{end + 1} = l;
  out.cr_x{end + 1} = x; out.cr_y{end + 1} = y;
  out.cr_err{end + 1} = err; out.cr_warn{end + 1} = lastwarn();
end

cd(old);
rmpath(fullfile(here, 'drawdot_shim'));
save('-v7', outfile, '-struct', 'out');
