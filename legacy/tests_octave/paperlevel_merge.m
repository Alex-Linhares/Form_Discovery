function paperlevel_merge(outfile, parts)
% Merge the per-job files written by fx_paperlevel(part, jobs) (cell array of paths)
% into one fixture with the runs in job order (used by legacy/tools/gen_paperlevel.py).
runs = {};
for k = 1:numel(parts)
  s = load(parts{k});
  runs = [runs, s.runs];
end
jobs = cellfun(@(r) r.job, runs);
[~, o] = sort(jobs);
runs = runs(o);
save('-v7', outfile, 'runs');
end
