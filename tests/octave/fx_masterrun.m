function fx_masterrun(outfile)
% Fixture for item 29 (L5-b): the masterrun.m script itself (unmodified), run once in a
% temporary directory, with every randperm draw recorded through the shim
% (matlab/octave_shims/randperm.m, pass-through + FD_RANDPERM_LOG), graph_like replaced
% by glc_spy.m (every slow call of the whole script) and choose_node_split by cns_spy.m
% (every call), as in fx_runmodel.m. GLREC.on stays set for the whole script, so gl, cns
% and logtext hold the 9 runs (chain, ring, tree x demo 1-3, in masterrun's order)
% one after the other.
%
% Headless: a system.m shim answers masterrun's `which neato` probe (masterrun.m:15)
% with "not found", so the ps.show* flags stay 0; every other command goes to the
% built-in. setps builds ps.dlocs from pwd, so the temporary directory gets a `data`
% symlink to the repo's data/. save_default_options('-v7') makes
% masterrun's own resultsdemo.mat readable by scipy.
%
% Saved: logtext, gl, cns; the variables of the resultsdemo.mat that masterrun wrote
% (modellike, structure, names, pss, llhistory; empty cells as they are); the size of
% each cell; order (1-based [sind dind] of the runs, masterrun.m:52-56); files (the
% growth-history files under results/, relative paths, Octave's names without .mat).
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = canonicalize_file_name(fullfile(root, 'matlab', 'formdiscovery1.0'));
sdir = fullfile(root, 'matlab', 'octave_shims');
addpath(mdir);
addpath(here);
addpath(sdir);                 % prepended: the shim shadows the built-in
olddir = pwd;
more off;
tmp = tempname(); mkdir(tmp);
lg = fullfile(tmp, 'log.txt');
work = fullfile(tmp, 'work'); mkdir(work);
symlink(canonicalize_file_name(fullfile(root, 'data')), fullfile(work, 'data'));

spydir = tempname(); mkdir(spydir);
rename(mdir, spydir, 'graph_like', 'function [logI graph] = graph_like(', ...
       'function [logI graph] = graph_like_orig(', ...
       {'function [logI, graph] = graph_like(data, graph, ps)', ...
        '[logI, graph] = glc_spy(data, graph, ps);'});
rename(mdir, spydir, 'choose_node_split', '=choose_node_split(graph, compind,', ...
       '=choose_node_split_orig(graph, compind,', ...
       {'function [ll, part1, part2, newgraph] = choose_node_split(graph, compind, splitind, pind, data, ps)', ...
        '[ll, part1, part2, newgraph] = cns_spy(graph, compind, splitind, pind, data, ps);'});
fid = fopen(fullfile(spydir, 'system.m'), 'w');
fprintf(fid, '%s\n', 'function varargout = system(cmd, varargin)', ...
        '% fx_masterrun: headless answer to masterrun.m''s neato probe', ...
        'if strcmp(cmd, ''which neato''), varargout = {1, ''''}; return; end', ...
        '[varargout{1:max(nargout, 1)}] = builtin(''system'', cmd, varargin{:});', 'end');
fclose(fid);
% a verbatim copy, called by name (Octave's run() would cd into the source directory)
copyfile(fullfile(mdir, 'masterrun.m'), fullfile(spydir, 'masterrun.m'));
addpath(spydir, '-begin');
global GLREC

randperm_config('', lg);
GLREC = struct('on', 1, 'list', {{}}, 'cns', {{}});
save_default_options('-v7');
cd(work);
t0 = tic;
try
  evalc('run_masterrun(mdir);');
catch err
  cd(olddir); rethrow(err);
end
secs = toc(t0);
cd(olddir);
GLREC.on = 0;

out = struct();
out.logtext = fileread(lg);
out.gl = GLREC.list;
out.cns = GLREC.cns;
m = load(fullfile(work, 'resultsdemo.mat'));
out.modellike = m.modellike;
out.structure = m.structure;
out.structure_size = size(m.structure);
out.names = m.names;
out.names_size = size(m.names);
out.llhistory = m.llhistory;
out.llhistory_size = size(m.llhistory);
% pss{sind,dind,rind} is masterrun's own ps (not runmodel's): keep the fields a
% Python test can check, per run
[si, di] = ndgrid([2, 4, 6], 1:3);
out.order = [si(:), di(:)];
pchk = {};
for k = 1:size(out.order, 1)
  p = m.pss{out.order(k, 1), out.order(k, 2), 1};
  pchk{end + 1} = struct('speed', p.speed, 'init', p.init, ...
                         'reloutsideinit', p.reloutsideinit, ...
                         'showinferredgraph', p.showinferredgraph, ...
                         'showpostclean', p.showpostclean, ...
                         'hasrunps', isfield(p, 'runps'));
end
out.pss_check = pchk;
out.pss_size = size(m.pss);
out.files = histories(fullfile(work, 'results'), '');
out.seconds = secs;

randperm_config();
rmpath(spydir);
confirm_recursive_rmdir(false, 'local');
rmdir(spydir, 's');
unlink(fullfile(work, 'data'));
rmdir(tmp, 's');
rmpath(sdir);                  % leave a shared (live-test) session with the built-in
clear('randperm', 'graph_like', 'choose_node_split', 'system', 'masterrun');
printf('fx_masterrun: %d runs, %d slow calls, %d splits (%.1f s)\n', ...
       size(out.order, 1), numel(out.gl), numel(out.cns), secs);

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function run_masterrun(mdir)
% masterrun.m is a script: run it in its own workspace (pwd = the work directory)
masterrun;
end

function files = histories(root, rel)
% every growthhistory* file under ROOT (sorted, paths relative to ROOT)
files = {};
d = dir(root);
for k = 1:numel(d)
  if any(strcmp(d(k).name, {'.', '..'})), continue; end
  p = fullfile(root, d(k).name);
  if isempty(rel), q = d(k).name; else, q = [rel '/' d(k).name]; end
  if d(k).isdir
    files = [files, histories(p, q)];
  elseif strncmp(d(k).name, 'growthhistory', 13)
    files{end + 1} = q;
  end
end
end

function rename(mdir, spydir, fname, head, newhead, stub)
% <fname>_orig.m = <fname>.m with its header renamed; <fname>.m = STUB (a forwarder)
src = fileread(fullfile(mdir, [fname '.m']));
orig = strrep(src, head, newhead);
if strcmp(orig, src), error('fx_masterrun: could not rename %s', fname); end
fid = fopen(fullfile(spydir, [fname '_orig.m']), 'w'); fprintf(fid, '%s', orig); fclose(fid);
fid = fopen(fullfile(spydir, [fname '.m']), 'w'); fprintf(fid, '%s\n', stub{:}); fclose(fid);
end
