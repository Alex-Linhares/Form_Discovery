function baseline_merge(outdir, pairs, pairdirs)
% Merge per-pair run_baseline outputs into one resultsdemo.mat and timings.mat
% (used by tools/gen_baselines.py, loop0002 item 04).
%
%   outdir    directory for the merged resultsdemo.mat and timings.mat
%   pairs     n x 2 matrix of [sind, dind], in run_baseline's serial run order
%   pairdirs  cell array of n directories, pairdirs{k} written by
%             run_baseline(kind, pairs(k,1), pairs(k,2), pairdirs{k})
%
% Replays run_baseline's accumulation (rind = 1, the only repeat): timings in
% run order, and for each run that did not crash modellike, structure, names,
% pss and llhistory at (sind, dind, 1), taken from that pair's resultsdemo.mat.
% A crashed pair has no resultsdemo.mat, so its entries stay unset, as in the
% serial run. The results/ trees are copied by the Python tool.

save_default_options('-v7');
rind = 1;
timings = struct('structure', {}, 'data', {}, 'rind', {}, 'seconds', {}, ...
                 'll', {}, 'error', {});
have = false;
for k = 1:size(pairs, 1)
  sind = pairs(k, 1);
  dind = pairs(k, 2);
  t = load(fullfile(pairdirs{k}, 'timings.mat'));
  timings = [timings, t.timings];
  f = fullfile(pairdirs{k}, 'resultsdemo.mat');
  if ~exist(f, 'file'), continue; end
  s = load(f);
  modellike(sind, dind, rind) = s.modellike(sind, dind, rind);
  structure{sind, dind, rind} = s.structure{sind, dind, rind};
  names{dind} = s.names{dind};
  pss{sind, dind, rind} = s.pss{sind, dind, rind};
  llhistory{sind, dind, rind} = s.llhistory{sind, dind, rind};
  have = true;
end
if ~exist(outdir, 'dir'), mkdir(outdir); end
if have
  save(fullfile(outdir, 'resultsdemo.mat'), 'modellike', 'structure', 'names', ...
       'pss', 'llhistory');
end
save(fullfile(outdir, 'timings.mat'), 'timings');
end
