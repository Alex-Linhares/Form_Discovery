function fx_params(outfile)
% Fixture for item 09 (L1 params): setps, defaultps, setrunps, gridpriors, structcounts,
% graph_prior. Inputs are the data sets, fixed object counts and the committed baseline
% graphs; everything is deterministic. setps.m builds ps.dlocs from pwd, so the paths are
% saved relative to pwd (dlocs_rel) and dlocs itself is removed from the saved struct.
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'legacy', 'matlab', 'formdiscovery1.0');
addpath(mdir);
out = struct();

% --- setps / defaultps ---------------------------------------------------------------
ps0 = setps();
out.dlocs_rel = cellfun(@(s) s(length(pwd) + 2:end), ps0.dlocs, 'UniformOutput', false);
out.setps = rmfield(ps0, 'dlocs');
ps = defaultps(ps0);
out.defaultps = rmfield(ps, 'dlocs');

% --- setrunps on every data set ------------------------------------------------------
nd = numel(ps.data);
out.sr_nobjects = zeros(1, nd); out.sr_type = cell(1, nd); out.sr_dim = nan(1, nd);
out.sr_speed = zeros(1, nd); out.sr_init = cell(1, nd);
for dind = 1:nd
  d = load(fullfile(mdir, 'data', [ps.data{dind} '.mat']));
  [n, p] = setrunps(d.data, dind, ps);
  out.sr_nobjects(dind) = n; out.sr_type{dind} = p.runps.type;
  if isfield(p.runps, 'dim'), out.sr_dim(dind) = p.runps.dim; end
  out.sr_speed(dind) = p.speed; out.sr_init{dind} = p.init;
end
% featforce: a square matrix treated as features; a non-square one is always 'feat'
d = load(fullfile(mdir, 'data', 'colors.mat'));
pf = ps; pf.featforce = 1;
[n, p] = setrunps(d.data, 14, pf);
out.sr_featforce_nobjects = n; out.sr_featforce_type = p.runps.type;
out.sr_featforce_hasdim = isfield(p.runps, 'dim');
[n, p] = setrunps(zeros(3, 5), 1, ps);
out.sr_rect_nobjects = n; out.sr_rect_type = p.runps.type;
[n, p] = setrunps(zeros(4, 4), 2, ps);   % square -> similarity, dim from simdim{2}
out.sr_sq_nobjects = n; out.sr_sq_type = p.runps.type; out.sr_sq_dim = p.runps.dim;

% --- structcounts (and gridpriors through it) ----------------------------------------
out.sc_n = [1 2 3 8 12 14 28 33 35 40];
out.sc_T = cell(1, numel(out.sc_n)); out.sc_logps = cell(1, numel(out.sc_n));
out.sc_isreal = zeros(numel(out.sc_n), 10);
for k = 1:numel(out.sc_n)
  p = structcounts(out.sc_n(k), ps);
  out.sc_T{k} = p.T; out.sc_logps{k} = p.logps;
  out.sc_isreal(k, :) = cellfun(@isreal, p.logps);
end

% --- gridpriors directly, another theta ----------------------------------------------
out.gp_theta = 0.3;
out.gp_n = [1 2 5 9];
out.gp_grid = cell(1, numel(out.gp_n)); out.gp_cyl = cell(1, numel(out.gp_n));
for k = 1:numel(out.gp_n)
  n = out.gp_n(k);
  T = repmat(factorial(1:n), n, 1) .* stirling2(n, n);
  out.gp_grid{k} = gridpriors(n, out.gp_theta, T, 'grid');
  out.gp_cyl{k} = gridpriors(n, out.gp_theta, T, 'cylinder');
end
try
  gridpriors(3, 0.5, ones(3), 'bogus');
  out.gp_bogus_err = 0;
catch
  out.gp_bogus_err = 1;
end

% --- graph_prior for every structure name and cluster count --------------------------
maxn = 12;
p = structcounts(maxn, ps);
out.gr_maxn = maxn;
out.gr_types = [ps.structures, {'domtree', 'undirdomtree', 'undirdomtreenoself', ...
                'dirdomtreenoself'}];
out.gr_prior = cell(1, numel(out.gr_types));
out.gr_nillegal = cell(1, numel(out.gr_types));
for t = 1:numel(out.gr_types)
  type = out.gr_types{t};
  if any(strcmp(type, {'grid', 'cylinder'})), kmax = maxn^2; else, kmax = maxn; end
  out.gr_prior{t} = zeros(1, kmax); out.gr_nillegal{t} = zeros(1, kmax);
  for k = 1:kmax
    g = struct('type', type, 'adjcluster', zeros(k), 'illegal', []);
    if strcmp(type, 'tree')
      g.illegal = 1:floor((k - 1) / 2);   % internal tree nodes do not count
    end
    out.gr_nillegal{t}(k) = numel(g.illegal);
    out.gr_prior{t}(k) = graph_prior(g, p);
  end
end
try
  graph_prior(struct('type', 'bogus', 'adjcluster', 1, 'illegal', []), p);
  out.gr_bogus_err = 0;
catch
  out.gr_bogus_err = 1;
end

% --- graph_prior on the final baseline graphs, with ps rebuilt by structcounts ---------
out.bl_kind = {}; out.bl_ij = zeros(0, 2); out.bl_nobj = []; out.bl_gp = [];
for kind = {'feat', 'rel'}
  r = load(fullfile(root, 'tests', 'fixtures', 'baseline', kind{1}, 'resultsdemo.mat'));
  for i = 1:rows(r.structure)
    for j = 1:columns(r.structure)
      g = r.structure{i, j};
      if isstruct(g) && isfield(g, 'adjcluster')
        nobj = g.objcount;
        pb = structcounts(nobj, ps);
        out.bl_kind{end + 1} = kind{1}; out.bl_ij(end + 1, :) = [i j];
        out.bl_nobj(end + 1) = nobj; out.bl_gp(end + 1) = graph_prior(g, pb);
      end
    end
  end
end

out.octave_version = OCTAVE_VERSION;
save('-v7', outfile, '-struct', 'out');
end
