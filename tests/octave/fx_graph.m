function fx_graph(outfile, seedoffset)
% Fixture for item 11 (L2-a1): makeemptygraph and combinegraphs.
%
% me_*  makeemptygraph for the 24 ps.structures names (grid and cylinder included) plus the
%       four extra domtree names in makeemptygraph.m's case list, with 1 and 5 objects.
% bl_*  combinegraphs called directly on every graph in the committed baseline growth
%       histories (feat + rel; all single-component), zonly 0 and 1.
% pr_*  product graphs built from baseline components: for each feature demo, the final
%       chain component of chainout/<d> and the final ring component of ringout/<d> give a
%       cylinder (ring x chain) and a grid (chain x chain); combined with zonly 0/1 and
%       prodtied 0/1; one variant with objects marked missing (z = -1).
% cg_*  every combinegraphs call made while growing grid/cylinder graphs (and a few
%       single-component ones) by seeded split_node sequences, starting from
%       makeemptygraph and from the baseline products, with prodtied 0 and 1. The calls are
%       captured by a spy that shadows combinegraphs.m (input graph, options, output). The
%       Wcluster of the graph is given seeded random weights before each split so that the
%       'origgraph' copy path (prodtied = 0) copies distinct values.
% ki2_* KI-2: a product graph whose first / second component has a non-empty illegal.
% SEEDOFFSET (default 0) shifts the rand('state') seeds of the split sequences; the live
% test in tests/test_graph.py uses it to get fresh sequences.
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'matlab', 'formdiscovery1.0');
addpath(mdir);
ps = defaultps(setps());
out = struct();

% --- makeemptygraph -------------------------------------------------------------------
out.me_names = [ps.structures, {'domtree', 'dirdomtreenoself', 'undirdomtree', ...
                                'undirdomtreenoself'}];
out.me_nobj = [1 5];
out.me_graphs = cell(numel(out.me_nobj), numel(out.me_names));
for k = 1:numel(out.me_nobj)
  for t = 1:numel(out.me_names)
    p = ps; p.runps.structname = out.me_names{t}; p.runps.nobjects = out.me_nobj(k);
    p.runps.type = 'feat';
    out.me_graphs{k, t} = makeemptygraph(p);
  end
end
try
  p = ps; p.runps.structname = 'bogus'; p.runps.nobjects = 3; p.runps.type = 'feat';
  makeemptygraph(p);
  out.me_bogus_err = 0;
catch
  out.me_bogus_err = 1;
end

% --- combinegraphs on the baseline growth histories -----------------------------------
files = {};
for kind = {'feat', 'rel'}
  d0 = fullfile(root, 'tests', 'fixtures', 'baseline', kind{1}, 'results');
  outs = dir(d0);
  for a = 1:numel(outs)
    if outs(a).name(1) == '.', continue; end
    sets = dir(fullfile(d0, outs(a).name));
    for b = 1:numel(sets)
      if sets(b).name(1) == '.', continue; end
      fs = dir(fullfile(d0, outs(a).name, sets(b).name, 'growthhistory*.mat'));
      for f = 1:numel(fs)
        files{end + 1} = fullfile(kind{1}, 'results', outs(a).name, sets(b).name, fs(f).name);
      end
    end
  end
end
files = sort(files);
out.bl_file = {}; out.bl_step = []; out.bl_in = {}; out.bl_out0 = {}; out.bl_out1 = {};
for f = 1:numel(files)
  h = load(fullfile(root, 'tests', 'fixtures', 'baseline', files{f}));
  bg = h.bestgraph; if ~iscell(bg), bg = {bg}; end
  for s = 1:numel(bg)
    g = bg{s};
    if ~isstruct(g), continue; end
    out.bl_file{end + 1} = files{f}; out.bl_step(end + 1) = s;
    out.bl_in{end + 1} = g;
    out.bl_out0{end + 1} = combinegraphs(g, ps);
    out.bl_out1{end + 1} = combinegraphs(g, ps, 'zonly', 1);
  end
end

% --- product graphs from baseline components ------------------------------------------
dsets = {'demo_chain_feat1', 'demo_ring_feat1', 'demo_tree_feat1'};
out.pr_name = {}; out.pr_in = {}; out.pr_out = {};
out.pr_zonly = []; out.pr_prodtied = [];
prods = {};
for d = 1:numel(dsets)
  gc = lastgraph(root, fullfile('feat', 'results', 'chainout', dsets{d}));
  gr = lastgraph(root, fullfile('feat', 'results', 'ringout', dsets{d}));
  cyl = gc; cyl.type = 'cylinder'; cyl.ncomp = 2;
  cyl.components = {gr.components{1}, gc.components{1}};
  grid = gc; grid.type = 'grid'; grid.ncomp = 2;
  grid.components = {gc.components{1}, gc.components{1}};
  miss = cyl; miss.z([2 5]) = -1;
  cand = {cyl, grid, miss};
  cname = {'cylinder', 'grid', 'cylinder_missing'};
  for c = 1:numel(cand)
    for zonly = 0:1
      gin = cand{c};
      if zonly
        % 'zonly' keeps Wcluster, so it needs an already combined graph; move object 1
        % to another cluster of component 2 (as swapobjclust/add_element do)
        gin = combinegraphs(gin, ps);
        n2 = gin.components{2}.nodecount;
        gin.components{2}.z(1) = 1 + mod(gin.components{2}.z(1), n2);
      end
      for pt = 0:1
        p = ps; p.prodtied = pt;
        out.pr_name{end + 1} = [dsets{d} ':' cname{c}];
        out.pr_in{end + 1} = gin;
        out.pr_zonly(end + 1) = zonly; out.pr_prodtied(end + 1) = pt;
        out.pr_out{end + 1} = combinegraphs(gin, p, 'zonly', zonly);
      end
    end
  end
  prods{end + 1} = combinegraphs(cyl, ps);
  prods{end + 1} = combinegraphs(grid, ps);
end

% --- combinegraphs calls captured during split_node sequences -------------------------
spydir = make_spy(mdir);
addpath(spydir, '-begin');
global CG_LOG
CG_LOG = {};
out.cg_seq = {}; out.cg_seqid = [];
seqid = 0;
starts = {};
for t = {'grid', 'cylinder', 'chain', 'ring', 'tree'}
  p = ps; p.runps.structname = t{1}; p.runps.nobjects = 12; p.runps.type = 'feat';
  starts{end + 1} = {[t{1} ':empty'], makeemptygraph(p)};
end
for k = 1:numel(prods)
  starts{end + 1} = {sprintf('baseline_product%d', k), prods{k}};
end
for pt = 0:1
  p = ps; p.prodtied = pt; p.runps.type = 'feat';
  for s = 1:numel(starts)
    seqid = seqid + 1;
    rand('state', seedoffset + 100 * pt + s);
    g = starts{s}{2};
    p.runps.structname = g.type; p.runps.nobjects = g.objcount;
    nsplit = 6;
    for step = 1:nsplit
      % seeded untied weights, so that the origgraph copy path moves real values
      g.Wcluster = g.adjcluster .* (0.5 + rand(size(g.adjcluster)));
      i = 1 + (g.ncomp > 1) * (rand() > 0.5);
      comp = g.components{i};
      cands = [];
      for c = 1:comp.nodecount
        if sum(comp.z == c) >= 2, cands(end + 1) = c; end
      end
      if strcmp(comp.type, 'tree')   % only leaves hold objects
        cands = cands(sum(comp.adj(cands, :), 2)' == 0);
      end
      if isempty(cands), break; end
      c = cands(1 + floor(rand() * numel(cands)));
      members = find(comp.z == c);
      [~, o] = sort(rand(1, numel(members)));
      members = members(o);
      m = 1 + floor(rand() * (numel(members) - 1));
      n0 = numel(CG_LOG);
      [g2, c1, c2] = evalc_split(g, i, c, 1, members(1:m), members(m + 1:end), p);
      if ~isstruct(g2), break; end
      for q = n0 + 1:numel(CG_LOG)
        CG_LOG{q}.seq = seqid; CG_LOG{q}.prodtied = pt;
      end
      g = g2;
    end
    out.cg_seq{seqid} = [starts{s}{1} sprintf(':prodtied%d', pt)];
  end
end
rmpath(spydir);
% the makeemptygraph calls above are captured too (no seq field): tag them seq 0
out.cg_in = {}; out.cg_out = {}; out.cg_zonly = []; out.cg_prodtied = [];
out.cg_hasorig = []; out.cg_orig = {}; out.cg_compind = []; out.cg_imap = {};
out.cg_seqid = [];
for q = 1:numel(CG_LOG)
  L = CG_LOG{q};
  a = L.args; opt = struct('origgraph', [], 'compind', 0, 'imap', [], 'zonly', 0);
  for j = 1:2:numel(a), opt.(a{j}) = a{j + 1}; end
  out.cg_in{end + 1} = L.graph; out.cg_out{end + 1} = L.out;
  out.cg_zonly(end + 1) = opt.zonly; out.cg_prodtied(end + 1) = L.ps_prodtied;
  out.cg_hasorig(end + 1) = ~isempty(opt.origgraph);
  if isempty(opt.origgraph), out.cg_orig{end + 1} = 0; else, out.cg_orig{end + 1} = opt.origgraph; end
  out.cg_compind(end + 1) = opt.compind; out.cg_imap{end + 1} = opt.imap;
  if isfield(L, 'seq'), out.cg_seqid(end + 1) = L.seq; else, out.cg_seqid(end + 1) = 0; end
end
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');

% --- KI-2: non-empty illegal in a product component -----------------------------------
g0 = prods{1};
g1 = g0; g1.components{1}.illegal = [1 2];
r = combinegraphs(g1, ps);
out.ki2_first_illegal = r.illegal;           % dropped silently (overwritten at l.66)
out.ki2_first_isempty = isempty(r.illegal);
g2 = g0; g2.components{2}.illegal = [1];
try
  combinegraphs(g2, ps);
  out.ki2_second_err = 0; out.ki2_second_msg = '';
catch e
  out.ki2_second_err = 1; out.ki2_second_msg = e.message;   % index 0 at l.66
end

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function g = lastgraph(root, rel)
fs = dir(fullfile(root, 'tests', 'fixtures', 'baseline', rel, 'growthhistory*.mat'));
names = sort({fs.name});
h = load(fullfile(root, 'tests', 'fixtures', 'baseline', rel, names{end}));
bg = h.bestgraph; if ~iscell(bg), bg = {bg}; end
g = bg{end};
end

function [g, c1, c2] = evalc_split(g, i, c, pind, part1, part2, p)
% split_node prints the production name; keep the log quiet
[~, g, c1, c2] = evalc_wrap(@() split_node(g, i, c, pind, part1, part2, p));
end

function [txt, g, c1, c2] = evalc_wrap(f)
g = []; c1 = []; c2 = [];
txt = evalc('[g, c1, c2] = f();');
end

function spydir = make_spy(mdir)
% combinegraphs_orig.m = combinegraphs.m with the function renamed; combinegraphs.m = spy
spydir = tempname(); mkdir(spydir);
src = fileread(fullfile(mdir, 'combinegraphs.m'));
src = regexprep(src, '^function graph = combinegraphs\(', ...
                'function graph = combinegraphs_orig(', 'once');
fid = fopen(fullfile(spydir, 'combinegraphs_orig.m'), 'w'); fprintf(fid, '%s', src); fclose(fid);
spy = {'function graph = combinegraphs(graph, ps, varargin)'
       'global CG_LOG'
       'L = struct(); L.graph = graph; L.args = varargin; L.ps_prodtied = ps.prodtied;'
       'graph = combinegraphs_orig(graph, ps, varargin{:});'
       'L.out = graph; CG_LOG{end + 1} = L;'
       'end'};
fid = fopen(fullfile(spydir, 'combinegraphs.m'), 'w');
fprintf(fid, '%s\n', spy{:}); fclose(fid);
end
