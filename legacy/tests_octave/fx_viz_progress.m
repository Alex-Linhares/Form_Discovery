function fx_viz_progress(outfile)
% Fixture for item 32: the progress figures of runmodel.m (l.40-48 true graph, figure 1;
% l.182-191 inferred graph, figure 3), structurefit.m (l.85-95 pre-clean, figure 1;
% l.198-208 post-clean, figure 2) and best_split.m (l.151-162 best split, figure 3).
%
% Two whole runmodel runs, set up as in fx_runmodel.m (headless defaults, rand('state', 1),
% randperm draws logged through legacy/matlab/octave_shims/randperm.m, graph_like and
% choose_node_split wrapped by glc_spy.m/cns_spy.m so that Python can replay them), but
% with every ps.show* flag set to 1:
%   chain x demo_chain_feat (speed 54; demo_chain_feat stores the true adj) and
%   dirring x demo_ring_rel_bin (speed 54, reloutsideinit 'overd': relational branch).
% legacy/tests_octave/progress_shim/ shadows figure, clf, title, drawnow and draw_dot; each
% appends to a log, saved per run as ev (kind, value = figure number or title, adj and
% labels for draw_dot). The run records carry the fields test_runmodel.replay reads.
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
sdir = fullfile(root, 'legacy', 'matlab', 'octave_shims');
addpath(mdir);
addpath(here);
addpath(sdir);
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);
more off;
tmp = tempname(); mkdir(tmp);
lg = fullfile(tmp, 'log.txt');

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
addpath(fullfile(here, 'progress_shim'), '-begin');
assert(strcmp(fileparts(which('draw_dot')), fullfile(here, 'progress_shim')));
global GLREC PROGRESS_LOG

specs = {{'chain', 1}, {'dirring', 4}};
runs = {};
for r = 1:numel(specs)
  s = specs{r};
  sind = find(strcmp(ps0.structures, s{1}), 1);
  dind = s{2};
  cd(mdir); ps = defaultps(setps()); cd(olddir);
  ps.showtruegraph = 1; ps.showinferredgraph = 1; ps.showbestsplit = 1;
  ps.showpreclean = 1; ps.showpostclean = 1;
  ps.speed = 54;
  if dind >= 4, ps.reloutsideinit = 'overd'; end
  base = fullfile(tmp, sprintf('r%d', r)); mkdir(base);
  randperm_config('', lg);
  GLREC = struct('on', 1, 'list', {{}}, 'cns', {{}});
  PROGRESS_LOG = {};
  cd(base);
  rand('state', 1);
  try
    evalc('[ll, graph, names, glls, bg] = runmodel(ps, sind, dind, 1);');
  catch err
    cd(olddir); rethrow(err);
  end
  cd(olddir);
  GLREC.on = 0;
  ev = struct('kind', {}, 'value', {}, 'adj', {}, 'labels', {});
  for k = 1:numel(PROGRESS_LOG)
    e = PROGRESS_LOG{k};
    v = ''; a = []; l = {};
    switch e{1}
      case 'figure', v = e{2};
      case 'title', v = e{2};
      case 'draw_dot', a = e{2}; l = e{3};
    end
    ev(end + 1) = struct('kind', e{1}, 'value', v, 'adj', a, 'labels', {l});
  end
  rec = struct('struct', s{1}, 'data', ps.data{dind}, 'sind', sind, 'dind', dind, ...
               'speed', 54, 'init', '', 'outsideinit', 0, ...
               'logtext', fileread(lg), 'out_ll', ll, 'out_graph', graph);
  rec.gl = GLREC.list;
  rec.cns = GLREC.cns;
  rec.out_names = names;
  rec.ev = ev;
  runs{end + 1} = rec;
  printf('fx_viz_progress: %s:%s ll = %.10g, %d display calls\n', s{1}, ps.data{dind}, ...
         ll, numel(ev));
end
randperm_config();
rmpath(fullfile(here, 'progress_shim'));
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
rmpath(sdir);
clear('randperm', 'graph_like', 'choose_node_split', 'draw_dot', 'figure', 'clf', ...
      'title', 'drawnow');
out = struct();
out.runs = runs;
out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function rename(mdir, spydir, fname, head, newhead, stub)
% as in fx_runmodel.m: <fname>_orig.m = <fname>.m with its header renamed;
% <fname>.m = STUB (a forwarder)
src = fileread(fullfile(mdir, [fname '.m']));
orig = strrep(src, head, newhead);
if strcmp(orig, src), error('fx_viz_progress: could not rename %s', fname); end
fid = fopen(fullfile(spydir, [fname '_orig.m']), 'w'); fprintf(fid, '%s', orig); fclose(fid);
fid = fopen(fullfile(spydir, [fname '.m']), 'w'); fprintf(fid, '%s\n', stub{:}); fclose(fid);
end
