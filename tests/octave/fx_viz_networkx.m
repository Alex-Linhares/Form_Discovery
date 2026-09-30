function fx_viz_networkx(outfile)
% Fixture for item 33 (viz/networkx_backend.py): what to_networkx must preserve of the
% final graphs of the committed baselines (9 feature + 54 relational runs,
% tests/fixtures/baseline/*/resultsdemo.mat), 63 graphs in all.
%
% For each graph: nx_run ('feat'/'rel' sind dind), nx_type, nx_objcount, nx_z (1-based,
% -1 missing), nx_names, nx_adj, nx_W, nx_Wsym, nx_sigma;
% nx_ei/nx_ej/nx_ew: [ei, ej] = find(graph.adj) (1-based, column-major) and
%   graph.W at those entries; nx_elen = 1 ./ nx_ew (the networkx 'weight');
% nx_si/nx_sj/nx_sw: the same for tril(graph.adjsym) (each undirected pair once);
% nx_L: the graph Laplacian of inv_covariance(graph.Wsym, ...) (inv_covariance.m:6-8),
%   the matrix the feature likelihood is built on (dataprobwsig.m:82);
% nx_deg: sum(graph.adjsym, 2) (node degrees of the undirected graph).
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'matlab', 'formdiscovery1.0');
olddir = cd(mdir); ps = defaultps(setps()); cd(olddir);   % setps builds ps.dlocs from pwd

out = struct();
f = {'run', 'type', 'objcount', 'z', 'names', 'adj', 'W', 'Wsym', 'sigma', 'ei', 'ej', ...
     'ew', 'elen', 'si', 'sj', 'sw', 'L', 'deg'};
for k = 1:numel(f), out.(['nx_' f{k}]) = {}; end
for kind = {'feat', 'rel'}
  r = load(fullfile(root, 'tests', 'fixtures', 'baseline', kind{1}, 'resultsdemo.mat'));
  for dind = 1:size(r.structure, 2)
    for sind = 1:size(r.structure, 1)
      g = r.structure{sind, dind, 1};
      if ~isstruct(g), continue; end
      adj = full(double(g.adj)); W = full(g.W); Wsym = full(g.Wsym);
      [ei, ej] = find(adj);
      ew = W(find(adj));
      [si, sj] = find(tril(full(double(g.adjsym))));
      sw = Wsym(sub2ind(size(Wsym), si, sj));
      [J, L] = inv_covariance(Wsym, g.objcount, g.sigma, ps);
      v = {sprintf('%s %d %d', kind{1}, sind, dind), g.type, g.objcount, g.z, ...
           r.names{dind}, adj, W, Wsym, g.sigma, ei, ej, ew, 1 ./ ew, si, sj, sw, L, ...
           sum(full(double(g.adjsym)), 2)};
      for q = 1:numel(f), out.(['nx_' f{q}]){end + 1} = v{q}; end
    end
  end
end
out.octave_version = OCTAVE_VERSION();
save('-v7', outfile, '-struct', 'out');
end
