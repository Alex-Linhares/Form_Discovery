function fx_dot_to_graph(outfile)
% Fixture: dot_to_graph (patched, see legacy/matlab/PATCHES.md) on the layout files in
% tests/fixtures/dot_to_graph/. lay1-4 are Graphviz 14 neato layouts of
% chain6 / ring12 / directed tree7 / chain6 + singleton; old1-2 are hand-written
% layouts in the pre-2.30 single-line integer format (old2 is directed, with a
% C comment). Saves A<k>, labels<k> (char matrix), x<k>, y<k>, files.
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
fxdir = fullfile(here, '..', '..', 'tests', 'fixtures', 'dot_to_graph');
files = {'lay1.dot', 'lay2.dot', 'lay3.dot', 'lay4.dot', 'old1.dot', 'old2.dot'};
out = struct();
out.files = char(files);
for k = 1:numel(files)
  [A, l, x, y] = dot_to_graph(fullfile(fxdir, files{k}));
  out.(sprintf('A%d', k)) = A;
  out.(sprintf('labels%d', k)) = char(l);
  out.(sprintf('x%d', k)) = x;
  out.(sprintf('y%d', k)) = y;
end
save('-v7', outfile, '-struct', 'out');
