function fx_runmodel(outfile, seedoffset)
% Fixture for item 28 (L5-a): runmodel (+ brlencases), with every randperm draw of a
% whole run recorded through the shim (matlab/octave_shims/randperm.m, pass-through +
% FD_RANDPERM_LOG) so that Python can replay it (formdiscovery.rng.parse_queue).
%
% Each run is one runmodel call as in matlab/run_baseline.m (headless ps,
% rand('state', 1 + SEEDOFFSET), relational runs with reloutsideinit 'overd'), with
% graph_like replaced by glc_spy.m (records every slow, ps.fast == 0, call of the run,
% including runmodel's own speed-5 "true score", l.174-179) and choose_node_split by
% cns_spy.m (records every call, to check tied choices). The originals are copied to
% <name>_orig.m in a temporary directory. GLREC.on stays set for the whole run.
%
% ds    the data sets after runmodel's preprocessing (setrunps + scaledata); feature data
%       are stored, Python loads the relational ones.
% runs  one record per run: struct/data names, sind/dind (1-based, into ps.structures,
%       which gets griddimsearch, cyldimsearchring and cyldimsearchchain appended, and
%       ps.data), the ps changes (speed, init, outsideinit), logtext (the draws), gl and
%       cns, the outputs (out_ll, out_graph, out_names, out_glls/out_bestgraph with their
%       cell sizes glls_size/bg_size), and the growth-history files written under the
%       run directory (files, relative, as Octave names them without .mat; files_lls
%       their bestgraphlls).
% SEEDOFFSET (default 0) shifts the rand('state') seed of every run (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'matlab', 'formdiscovery1.0');
sdir = fullfile(root, 'matlab', 'octave_shims');
addpath(mdir);
addpath(here);
addpath(sdir);                 % prepended: the shim shadows the built-in
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd
out = struct();
more off;
tmp = tempname(); mkdir(tmp);
lg = fullfile(tmp, 'log.txt');

ds = {};
for k = 1:5
  [d, p] = prep(ps0, k, mdir);
  r = struct('name', ps0.data{k}, 'type', p.runps.type);
  if ~strcmp(p.runps.type, 'rel'), r.data = d; end
  ds{end + 1} = r;
end
out.ds = ds;

spydir = tempname(); mkdir(spydir);
rename(mdir, spydir, 'graph_like', 'function [logI graph] = graph_like(', ...
       'function [logI graph] = graph_like_orig(', ...
       {'function [logI, graph] = graph_like(data, graph, ps)', ...
        '[logI, graph] = glc_spy(data, graph, ps);'});
rename(mdir, spydir, 'choose_node_split', '=choose_node_split(graph, compind,', ...
       '=choose_node_split_orig(graph, compind,', ...
       {'function [ll, part1, part2, newgraph] = choose_node_split(graph, compind, splitind, pind, data, ps)', ...
        '[ll, part1, part2, newgraph] = cns_spy(graph, compind, splitind, pind, data, ps);'});
addpath(spydir, '-begin');
global GLREC

% an outside start graph (ps.outsideinit, runmodel.m:52-53): a two-cluster chain on
% demo_chain_feat, saved as the only variable of a .mat file
p = ps0; p.runps.structname = 'chain';
[nobj, p] = setrunps(ds{1}.data, 1, p);
p = structcounts(nobj, p);
graph = split_node(makeemptygraph(p), 1, 1, 1, 1:4, 5:nobj, p);
initfile = fullfile(tmp, 'outsideinit.mat');
save('-v7', initfile, 'graph');
out.outsideinit_graph = graph;

% {structure, dind, speed, init ('' = default), outsideinit (0/1)}
specs = {{'chain', 1, 54, '', 0}, {'ring', 1, 54, '', 0}, {'tree', 1, 54, '', 0}, ...
         {'chain', 2, 54, '', 0}, {'ring', 2, 54, '', 0}, {'tree', 2, 54, '', 0}, ...
         {'chain', 3, 54, '', 0}, {'ring', 3, 54, '', 0}, {'tree', 3, 54, '', 0}, ...
         {'dirring', 4, 54, '', 0}, {'partition', 5, 54, '', 0}, ...
         {'chain', 1, 5, '', 0}, {'tree', 3, 5, '', 0}, ...
         {'ring', 2, 5, 'none', 0}, {'chain', 1, 5, 'ext', 0}, {'chain', 2, 5, 'int', 0}, ...
         {'griddimsearch', 1, 54, '', 0}, {'griddimsearch', 2, 5, '', 0}, ...
         {'cyldimsearchring', 2, 54, '', 0}, {'cyldimsearchchain', 1, 5, '', 0}, ...
         {'chain', 1, 5, '', 1}};
structs = [ps0.structures, {'griddimsearch', 'cyldimsearchring', 'cyldimsearchchain'}];
runs = {};
for r = 1:numel(specs)
  s = specs{r};
  sind = find(strcmp(structs, s{1}), 1);
  dind = s{2};
  cd(mdir); ps = defaultps(setps()); cd(olddir);
  ps.structures = structs;
  ps.showtruegraph = 0; ps.showinferredgraph = 0; ps.showbestsplit = 0;
  ps.showpreclean = 0; ps.showpostclean = 0;
  ps.speed = s{3};
  if ~isempty(s{4}), ps.init = s{4}; end
  if s{5}, ps.outsideinit = initfile; end
  if dind >= 4, ps.reloutsideinit = 'overd'; end
  base = fullfile(tmp, sprintf('r%d', r)); mkdir(base);
  randperm_config('', lg);
  GLREC = struct('on', 1, 'list', {{}}, 'cns', {{}});
  cd(base);
  rand('state', 1 + seedoffset);
  t0 = tic;
  try
    evalc('[ll, graph, names, glls, bg] = runmodel(ps, sind, dind, 1);');
  catch err
    cd(olddir); rethrow(err);
  end
  secs = toc(t0);
  cd(olddir);
  GLREC.on = 0;
  [files, flls] = histories(base, '');
  rec = struct('struct', s{1}, 'data', ps.data{dind}, 'sind', sind, 'dind', dind, ...
               'speed', s{3}, 'init', s{4}, 'outsideinit', s{5}, ...
               'logtext', fileread(lg), 'out_ll', ll, 'out_graph', graph, ...
               'glls_size', size(glls), 'bg_size', size(bg), 'seconds', secs);
  rec.gl = GLREC.list;
  rec.cns = GLREC.cns;
  rec.out_names = names;
  rec.out_glls = glls;
  rec.out_bestgraph = bg;
  rec.files = files;
  rec.files_lls = flls;
  runs{end + 1} = rec;
  printf('fx_runmodel: %s:%s speed %d init %s: ll = %.10g (%.1f s, %d slow)\n', s{1}, ...
         ps.data{dind}, s{3}, s{4}, ll, secs, numel(rec.gl));
end
randperm_config();
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.runs = runs;
rmpath(sdir);                  % leave a shared (live-test) session with the built-in
clear('randperm', 'graph_like', 'choose_node_split');

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function [files, lls] = histories(root, rel)
% every growthhistory* file under ROOT (sorted, paths relative to ROOT) and its
% bestgraphlls
files = {}; lls = {};
d = dir(root);
for k = 1:numel(d)
  if any(strcmp(d(k).name, {'.', '..'})), continue; end
  p = fullfile(root, d(k).name);
  if isempty(rel), q = d(k).name; else, q = [rel '/' d(k).name]; end
  if d(k).isdir
    [f, l] = histories(p, q);
    files = [files, f]; lls = [lls, l];
  elseif strncmp(d(k).name, 'growthhistory', 13)
    s = load(p);
    files{end + 1} = q; lls{end + 1} = s.bestgraphlls;
  end
end
end

function [data, ps] = prep(ps, dind, mdir)
% runmodel.m:27-95 without the graph initialisation
names = [];
olddir = pwd; cd(mdir); load(ps.dlocs{dind}); cd(olddir);
[nobjects, ps] = setrunps(data, dind, ps);
[data, ps] = scaledata(data, ps);
end

function rename(mdir, spydir, fname, head, newhead, stub)
% <fname>_orig.m = <fname>.m with its header renamed; <fname>.m = STUB (a forwarder)
src = fileread(fullfile(mdir, [fname '.m']));
orig = strrep(src, head, newhead);
if strcmp(orig, src), error('fx_runmodel: could not rename %s', fname); end
fid = fopen(fullfile(spydir, [fname '_orig.m']), 'w'); fprintf(fid, '%s', orig); fclose(fid);
fid = fopen(fullfile(spydir, [fname '.m']), 'w'); fprintf(fid, '%s\n', stub{:}); fclose(fid);
end
