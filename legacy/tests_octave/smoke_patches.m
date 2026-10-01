function out = smoke_patches(matlabdir)
% Smoke test for the Octave compatibility patches (item 03, legacy/matlab/PATCHES.md).
% setps; defaultps; structcounts(12, ps); makeemptygraph for every structure
% name; scaledata on demo_chain_feat; dijkstra (narginchk).
% Returns a struct; errors propagate to the caller.
olddir = pwd;
cleanup = onCleanup(@() cd(olddir));
cd(matlabdir);                    % setps builds data paths from pwd
ps = setps();
ps = defaultps(ps);
ps = structcounts(12, ps);
out.nlogps = numel(ps.logps);

names = ps.structures;           % includes grid and cylinder
out.structures = names;
out.graph_ok = zeros(1, numel(names));
out.graph_ncomp = zeros(1, numel(names));
for i = 1:numel(names)
  p = ps;
  p.runps.structname = names{i};
  p.runps.nobjects = 12;
  p.runps.type = 'feat';
  g = makeemptygraph(p);
  out.graph_ok(i) = isequal(size(g.adj), [13 13]) && g.objcount == 12;
  out.graph_ncomp(i) = g.ncomp;
end

load(ps.dlocs{1});                % demo_chain_feat: data, names
[nobjects, ps] = setrunps(data, 1, ps);
[sdata, ps] = scaledata(data, ps);
out.scaled_size = size(sdata);
out.scaled = sdata;
out.nobjects = nobjects;

A = [0 1 0; 1 0 1; 0 1 0];
out.dijkstra = dijkstra(A);
