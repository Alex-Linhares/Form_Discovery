function fx_paperlevel(outfile, jobs)
% Fixture for item 30 (PLAN.md 7.2): the paper-level form comparisons, run through the
% original runmodel.m (headless ps as in legacy/matlab/run_baseline.m, rand('state', seed) before
% each run; seed 1 unless noted, as masterrun.m does for rind = 1).
%
% Jobs (1-based sind/dind into ps.structures/ps.data):
%   1-25   synthetic data (masterrun.m's option a): partition, chain, ring, tree, grid
%          x synthpartition, synthchain, synthring, synthtree, synthgrid, at ps.speed = 5
%          (search at speed 5 only, then runmodel's slow "true score"; the default 54
%          adds a speed-4 pass that costs several times more on 40 x 2000 data);
%   26-41  animals and colors x the 8 feature forms (option b), default speed (54);
%   42-45  animals x tree, hierarchy with rand('state', 2) and rand('state', 3) (the
%          seed-1 tree search stops in a worse local optimum than the hierarchy's).
%
% JOBS (optional) runs only those job numbers. legacy/tools/gen_paperlevel.py runs the jobs in
% parallel Octave processes and merges the parts with paperlevel_merge.m.
%
% runs  one record per job: job, struct, data, sind, dind, speed, ll (runmodel's first
%       output), seed, graph (the final graph), ncl (distinct z), secs (wall clock).
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
addpath(mdir);
olddir = pwd;
cd(mdir); ps0 = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd
ps0.showtruegraph = 0; ps0.showinferredgraph = 0; ps0.showbestsplit = 0;
ps0.showpreclean = 0; ps0.showpostclean = 0;
more off;

specs = {};
for d = 7:11
  for s = [1, 2, 4, 6, 7]
    specs{end + 1} = [s, d, 5, 1];
  end
end
for d = [12, 14]
  for s = 1:8
    specs{end + 1} = [s, d, 54, 1];
  end
end
for seed = [2, 3]
  for s = [6, 5]
    specs{end + 1} = [s, 12, 54, seed];
  end
end
if nargin < 2 || isempty(jobs), jobs = 1:numel(specs); end

tmp = tempname(); mkdir(tmp);
cleanup = onCleanup(@() cd(olddir));
runs = {};
for j = jobs(:)'
  sp = specs{j};
  ps = ps0; ps.speed = sp(3);
  cd(tmp);                     % runmodel mkdirs/cds into results/ under pwd
  rand('state', sp(4));
  t0 = tic;
  [ll, graph] = runmodel(ps, sp(1), sp(2), 1);
  secs = toc(t0);
  cd(olddir);
  runs{end + 1} = struct('job', j, 'struct', ps.structures{sp(1)}, ...
                         'data', ps.data{sp(2)}, 'sind', sp(1), 'dind', sp(2), ...
                         'speed', sp(3), 'seed', sp(4), 'll', ll, 'graph', graph, ...
                         'ncl', numel(unique(graph.z)), 'secs', secs);
  printf('%d %s %s %.6f %.1f s\n', j, ps.structures{sp(1)}, ps.data{sp(2)}, ll, secs);
end
cd(olddir);
confirm_recursive_rmdir(0);
rmdir(tmp, 's');
save('-v7', outfile, 'runs');
end
