function timings = run_baseline(kind, thisstruct, thisdata)
% Headless Octave baseline for formdiscovery1.0 (PLAN.md section 3, item 04).
%
% Mirrors masterrun.m (same loop, same rand('state', rind) seeding, same
% resultsdemo.mat contents) with these differences:
%   - all ps.show* flags are 0 (no neato probe, no figures);
%   - results go to tests/fixtures/baseline/<kind>/ instead of the source dir;
%   - save_default_options('-v7') so resultsdemo.mat and the growth histories
%     are MAT v7 files readable by scipy (Octave's default is its text format);
%   - growth history files, which Octave saves without an extension, are
%     renamed to *.mat afterwards (MATLAB would have added .mat itself);
%   - resultsdemo.mat is written once per run without the retry/pause loop,
%     and wall-clock time per run is stored in timings.mat.
%
%   kind       'feat' (default): chain, ring, tree x demo feature sets 1-3.
%   thisstruct structure indices into ps.structures (optional override)
%   thisdata   dataset indices into ps.data (optional override)
%
% Run from anywhere:  octave-cli --eval "run(...)" or
%   cd matlab; octave-cli --eval "run_baseline('feat')"

if nargin < 1 || isempty(kind), kind = 'feat'; end

here = fileparts(mfilename('fullpath'));
srcdir = fullfile(here, 'formdiscovery1.0');
outdir = fullfile(here, '..', 'tests', 'fixtures', 'baseline', kind);
if ~exist(outdir, 'dir'), mkdir(outdir); end
outdir = canonicalize_file_name(outdir);

olddir = pwd;
cleanup = onCleanup(@() cd(olddir));
addpath(srcdir);
save_default_options('-v7');
more off;

cd(srcdir);            % setps builds ps.dlocs from pwd
ps = setps();
ps = defaultps(ps);
ps.showtruegraph     = 0;
ps.showinferredgraph = 0;
ps.showbestsplit     = 0;
ps.showpreclean      = 0;
ps.showpostclean     = 0;

switch kind
  case 'feat'
    defstruct = [2, 4, 6];
    defdata   = 1:3;
  otherwise
    error('run_baseline: unknown kind %s', kind);
end
if nargin < 2 || isempty(thisstruct), thisstruct = defstruct; end
if nargin < 3 || isempty(thisdata),   thisdata   = defdata;   end

cd(outdir);            % runmodel mkdirs results/<struct>out/<data><rind> here
masterfile = fullfile(outdir, 'resultsdemo.mat');
if exist(masterfile, 'file'), delete(masterfile); end
if exist(fullfile(outdir, 'results'), 'dir')
  confirm_recursive_rmdir(false, 'local');
  rmdir(fullfile(outdir, 'results'), 's');
end

sindpair = repmat(thisstruct', 1, length(thisdata));
dindpair = repmat(thisdata, length(thisstruct), 1);
sindpair = sindpair(:)';
dindpair = dindpair(:)';

timings = struct('structure', {}, 'data', {}, 'rind', {}, 'seconds', {}, ...
                 'll', {});
repeats = 1;
for rind = 1:repeats
  for ind = 1:length(dindpair)
    dind = dindpair(ind);
    sind = sindpair(ind);
    disp(['  ', ps.data{dind}, ' ', ps.structures{sind}]);
    rand('state', rind);
    t0 = tic;
    [mtmp stmp ntmp ltmp gtmp] = runmodel(ps, sind, dind, rind);
    secs = toc(t0);
    printf('  -> %s %s: ll = %.10g, %.1f s\n', ps.data{dind}, ...
           ps.structures{sind}, mtmp, secs);
    timings(end+1) = struct('structure', ps.structures{sind}, ...
                            'data', ps.data{dind}, 'rind', rind, ...
                            'seconds', secs, 'll', mtmp);
    if exist(masterfile, 'file')
      currps = ps; load(masterfile); ps = currps;
    end
    pss{sind,dind,rind} = ps;
    modellike(sind, dind, rind) = mtmp;
    structure{sind,dind, rind}  = stmp;
    names{dind} = ntmp;
    llhistory{sind, dind, rind} = ltmp;
    save(masterfile, 'modellike', 'structure', 'names', 'pss', 'llhistory');
    save(fullfile(outdir, 'timings.mat'), 'timings');
    fix_extensions(fullfile(outdir, 'results'));
  end
end
end

function fix_extensions(root)
% Octave's save() does not append .mat; rename growthhistory* files.
d = dir(root);
for k = 1:numel(d)
  if any(strcmp(d(k).name, {'.', '..'})), continue; end
  p = fullfile(root, d(k).name);
  if d(k).isdir
    fix_extensions(p);
  elseif strncmp(d(k).name, 'growthhistory', 13) && isempty(regexp(d(k).name, '\.mat$', 'once'))
    movefile(p, [p, '.mat']);
  end
end
end
