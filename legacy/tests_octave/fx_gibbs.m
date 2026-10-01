function fx_gibbs(outfile, seedoffset)
% Fixture for item 26 (L4-c1): gibbs_clean (+ nearmissopts), with every randperm draw
% recorded through the shim (legacy/matlab/octave_shims/randperm.m, pass-through +
% FD_RANDPERM_LOG) so that Python can replay it (formdiscovery.rng.parse_queue).
%
% The calls come from re-running runs with run_baseline.m's settings (speed 54: speed 5,
% then speed 4) while gibbs_clean is replaced by a spy (legacy/tests_octave/gibbs_spy.m; its
% header describes what is kept) and graph_like by a wrapper (legacy/tests_octave/glc_spy.m)
% that records the slow (ps.fast == 0) calls made inside gibbs_clean. The originals are
% copied to gibbs_clean_orig.m and graph_like_orig.m, and swapobjclust.m's subfunctions
% to swsub.m (used to perturb graphs), in a temporary directory.
%
% ds    the data sets after runmodel's preprocessing (as in fx_swap.m). Feature data
%       are stored; Python loads the relational ones.
% runs  structure:data of each run; run_ll its final score (the spy must not change it).
% calls kept calls: kind 'bl' (the real call), 'pt' (a perturbed graph) or 'g0'
%       (ps.gibbsclean = 0). The input graph, the options (opt, defaults filled in), the
%       ps fields that vary, the draws (logtext), the outputs (out_ll, out_graph) and the
%       slow graph_like calls (gl: graph, logI, out_graph, in call order).
% SEEDOFFSET (default 0) shifts the rand('state') seed of every run (live test).
if nargin < 2, seedoffset = 0; end
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
sdir = fullfile(root, 'legacy', 'matlab', 'octave_shims');
addpath(mdir);
addpath(here);
addpath(sdir);                 % prepended: the shim shadows the built-in
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd
out = struct();
more off;
tmp = tempname(); mkdir(tmp);
lg = fullfile(tmp, 'log.txt');

% --- ds: data sets ----------------------------------------------------------------------
dinds = [1 2 3 4 5 11];
ds = {};
for k = dinds
  [d, p] = prep(ps0, k, mdir);
  r = struct('name', ps0.data{k}, 'type', p.runps.type);
  if ~strcmp(p.runps.type, 'rel'), r.data = d; end
  ds{end + 1} = r;
end
out.ds = ds;

% --- spied runs -------------------------------------------------------------------------
spydir = tempname(); mkdir(spydir);
rename(mdir, spydir, 'gibbs_clean', 'function [ll graph] = gibbs_clean(', ...
       'function [ll graph] = gibbs_clean_orig(', ...
       {'function [ll, graph] = gibbs_clean(varargin)', ...
        '[ll, graph] = gibbs_spy(varargin{:});'});
rename(mdir, spydir, 'graph_like', 'function [logI graph] = graph_like(', ...
       'function [logI graph] = graph_like_orig(', ...
       {'function [logI, graph] = graph_like(data, graph, ps)', ...
        '[logI, graph] = glc_spy(data, graph, ps);'});
make_sub(mdir, spydir, 'swapobjclust', 'function [sw1 sw2]= chooseswaps', ...
         {'chooseswaps', 2; 'doswap', 1}, 'swsub');
addpath(spydir, '-begin');
global SPY GLREC
GLREC = struct('on', 0, 'list', {{}});
runs = {{'feat', 2, 1}, {'feat', 6, 3}, {'feat', 4, 2}, {'feat', 8, 2}, {'feat', 7, 11}, ...
        {'rel', 17, 4}, {'rel', 23, 5}};
calls = {};
out.runs = {}; out.run_ll = []; out.run_ncalls = [];
for r = 1:numel(runs)
  SPY = struct('calls', {{}}, 'n', 0, 'log', lg, 'run', r, 'kept', struct(), ...
               'keptch', struct());
  kind = runs{r}{1}; sind = runs{r}{2}; dind = runs{r}{3};
  randperm_config('', lg);
  out.run_ll(r) = spied_run(mdir, fullfile(tmp, kind), kind, sind, dind, 1 + seedoffset);
  out.runs{r} = [ps0.structures{sind} ':' ps0.data{dind}];
  out.run_ncalls(r) = SPY.n;
  calls = [calls, SPY.calls];
end
randperm_config();
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
rmdir(tmp, 's');
out.calls = calls;
rmpath(sdir);                  % leave a shared (live-test) session with the built-in
clear('randperm', 'graph_like', 'gibbs_clean');

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
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
if strcmp(orig, src), error('fx_gibbs: could not rename %s', fname); end
fid = fopen(fullfile(spydir, [fname '_orig.m']), 'w'); fprintf(fid, '%s', orig); fclose(fid);
fid = fopen(fullfile(spydir, [fname '.m']), 'w'); fprintf(fid, '%s\n', stub{:}); fclose(fid);
end

function make_sub(mdir, spydir, fname, subhead, subs, subfile)
% <subfile>.m = the subfunctions of <fname>.m (from SUBHEAD on) behind a dispatcher
% (as in fx_spr.m). SUBS lists {name, nargout}.
src = fileread(fullfile(mdir, [fname '.m']));
k = strfind(src, subhead);
if isempty(k), error('fx_gibbs: %s not found', subhead); end
lines = {sprintf('function varargout = %s(name, varargin)', subfile), 'switch name'};
for s = 1:size(subs, 1)
  outs = strjoin(arrayfun(@(m) sprintf('varargout{%d}', m), 1:subs{s, 2}, ...
                          'UniformOutput', false), ', ');
  lines{end + 1} = sprintf('  case ''%s'', [%s] = %s(varargin{:});', subs{s, 1}, outs, subs{s, 1});
end
lines{end + 1} = sprintf('  otherwise, error(''%s: unknown %%s'', name);', subfile);
lines{end + 1} = 'end';
lines{end + 1} = '';
fid = fopen(fullfile(spydir, [subfile '.m']), 'w');
fprintf(fid, '%s\n', lines{:});
fprintf(fid, '%s', src(k(1):end)); fclose(fid);
end

function ll = spied_run(mdir, outdir, kind, sind, dind, seed)
% one run as in legacy/matlab/run_baseline.m (headless ps, rand('state', seed), relational runs
% with reloutsideinit 'overd'); output goes to OUTDIR
olddir = pwd;
cd(mdir); ps = defaultps(setps());   % setps builds ps.dlocs from pwd
ps.showtruegraph = 0; ps.showinferredgraph = 0; ps.showbestsplit = 0;
ps.showpreclean = 0; ps.showpostclean = 0;
if strcmp(kind, 'rel'), ps.reloutsideinit = 'overd'; end
if ~exist(outdir, 'dir'), mkdir(outdir); end
cd(outdir);
rand('state', seed);
try
  evalc('ll = runmodel(ps, sind, dind, 1);');
catch err
  cd(olddir); rethrow(err);
end
cd(olddir);
end
