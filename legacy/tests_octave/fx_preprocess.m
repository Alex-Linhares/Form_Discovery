function fx_preprocess(outfile)
% Fixture for item 10 (L1 preprocess): scaledata (+makechunks), simpleshiftscale,
% makesimlike. scaledata runs on every data set with the defaults (datatransform
% 'simpleshiftscale', simtransform 'none'), on every feature set with 'makesimlike' and
% 'none', on every similarity set with simtransform 'center', and on colors with featforce.
% judges (Inf = missing) exercises the chunk path. Small constructed inputs cover the
% makesimlike "can't achieve a zero" branch, chunk ties in max(csize), and direct calls.
% Everything is deterministic (the random inputs use a fixed rand('state')).
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
addpath(mdir);
out = struct();
ps0 = defaultps(setps());

% --- scaledata on every data set ------------------------------------------------------
cases = {};
for dind = 1:numel(ps0.data)
  d = load(fullfile(mdir, 'data', [ps0.data{dind} '.mat']));
  [n, ps] = setrunps(d.data, dind, ps0);
  cfgs = {{'default', ps}};
  switch ps.runps.type
    case 'feat'
      p = ps; p.datatransform = 'makesimlike'; cfgs{end + 1} = {'makesimlike', p};
      p = ps; p.datatransform = 'none'; cfgs{end + 1} = {'none', p};
    case 'sim'
      p = ps; p.simtransform = 'center'; cfgs{end + 1} = {'center', p};
  end
  for k = 1:numel(cfgs)
    cases{end + 1} = runcase(ps0.data{dind}, dind, cfgs{k}{1}, d.data, cfgs{k}{2});
  end
end
% featforce: a similarity matrix treated as features
d = load(fullfile(mdir, 'data', 'colors.mat'));
p = ps0; p.featforce = 1;
[n, p] = setrunps(d.data, 14, p);
cases{end + 1} = runcase('colors', 14, 'featforce', d.data, p);
out.cases = cases;

% --- constructed inputs ---------------------------------------------------------------
rand('state', 10); randn('state', 10);
% identical rows: every (i, j) quadratic has no real root, so makesimlike takes the
% "can't achieve a zero" branch (ub == inf)
X = repmat([1 2 4 -1 3], 4, 1);
out.c_same = X;
p = ps0; p.missingdata = 0;
out.c_same_msl = makesimlike(X, p);
out.c_same_sss = simpleshiftscale(X, p);
% a constant row: delta == 0 exactly
X = [1 1 1 1; 0 2 -1 3; 2 0 1 -1];
out.c_const = X;
out.c_const_msl = makesimlike(X, p);
% direct calls on random data
X = randn(6, 10);
out.c_rand = X;
out.c_rand_msl = makesimlike(X, p);
out.c_rand_sss = simpleshiftscale(X, p);
% missing data with three chunks of 2 features each: max(csize) takes the first chunk
X = randn(5, 6) + 0.5;
X(1, 3:4) = Inf; X(2, 5:6) = Inf;
out.c_tie = X;
pr = ps0; pr.runps.type = 'feat';
out.c_tie_cases = {runcase('c_tie', 0, 'default', X, pr)};
pr.datatransform = 'makesimlike';
out.c_tie_cases{end + 1} = runcase('c_tie', 0, 'makesimlike', X, pr);
% missing data: four chunks, the largest (3 features) is a tie between chunks 3 and 4,
% and object 4 is observed only in the last chunk
X = randn(4, 9);
X(3, [1 4]) = Inf; X(:, 2) = [Inf; 1; Inf; 2]; X(4, :) = Inf; X(4, 7:9) = [0.5 -1 2];
out.c_miss = X;
pr = ps0; pr.runps.type = 'feat';
out.c_miss_cases = {runcase('c_miss', 0, 'default', X, pr)};
pr.datatransform = 'makesimlike';
out.c_miss_cases{end + 1} = runcase('c_miss', 0, 'makesimlike', X, pr);

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end

function c = runcase(name, dind, cfg, data, ps)
% scaledata on one input; records the output data and every field it may set.
c = struct('name', name, 'dind', dind, 'cfg', cfg);
[dout, pout] = scaledata(data, ps);
c.type = pout.runps.type;
c.has_missingdata = isfield(pout, 'missingdata');
if strcmp(c.type, 'rel')
  c.unchanged = isequal(dout, data) && isequal(pout, ps);
  return
end
c.data = dout;
c.missingdata = pout.missingdata;
f = {'SS', 'chunkcount', 'chunknum', 'featind', 'objind', 'chunksize', 'chunkSS'};
c.has = cellfun(@(x) isfield(pout.runps, x), f);
for k = 1:numel(f)
  if c.has(k)
    c.(['r_' f{k}]) = pout.runps.(f{k});
  end
end
end
