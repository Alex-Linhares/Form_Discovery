function fx_rng(outfile)
% Fixture for item 22: the randperm shim (matlab/octave_shims/randperm.m) that the
% Python providers in src/formdiscovery/rng.py mirror (PLAN.md §4.2).
%
% bi    pass-through. For rand('state', s), s = 1..3, the built-in randperm on SIZES
%       (ref), then the shim with FD_RANDPERM unset and a log (out, logtext). out must
%       equal ref: the shim leaves the Octave stream, and so the baselines, unchanged.
% id    FD_RANDPERM=identity on SIZES (out) and its log.
% qu    replay. The script writes a queue file (qtext; 7 permutations drawn by the
%       built-in after rand('state', 42), including an empty one), replays it (out)
%       and logs it (logtext). A rewind with randperm_config then replays from the first
%       entry again (rew). A switch to a second queue file reloads (sw).
% er    error messages: queue exhausted, length mismatch, an entry that is not a
%       permutation, a bad line header, randperm(n, m) in identity and queue mode.
% cs    a real call site: choose_seedpairs.m:24 on a top-level split of cluster 1
%       (7 members > 5, so each member draws randperm(6)). It runs under identity
%       (ident), under the built-in after rand('state', 3) with a log (rec, reclog),
%       and replaying that log (rep).
warning('off', 'all');
here = fileparts(mfilename('fullpath'));
root = fullfile(here, '..', '..');
mdir = fullfile(root, 'matlab', 'formdiscovery1.0');
sdir = fullfile(root, 'matlab', 'octave_shims');
addpath(mdir);
addpath(sdir);                 % prepended: the shim shadows the built-in
more off;
tmp = tempname(); mkdir(tmp);
lg = fullfile(tmp, 'log.txt');
out = struct();

SIZES = [5 1 0 8 3 12 2];
out.sizes = SIZES;

% --- bi: pass-through -----------------------------------------------------------------
bi = {};
for s = 1:3
  r = struct('seed', s);
  randperm_config();
  rand('state', s);
  r.ref = arrayfun(@(n) builtin('randperm', n), SIZES, 'UniformOutput', false);
  randperm_config('', lg);
  rand('state', s);
  r.out = arrayfun(@(n) randperm(n), SIZES, 'UniformOutput', false);
  r.logtext = fileread(lg);
  bi{end+1} = r;
end
out.bi = bi;

% --- id: identity ---------------------------------------------------------------------
randperm_config('identity', lg);
out.id = struct('out', {arrayfun(@(n) randperm(n), SIZES, 'UniformOutput', false)});
out.id.logtext = fileread(lg);

% --- qu: replay -----------------------------------------------------------------------
QS = [4 0 1 6 6 2 9];
randperm_config();
rand('state', 42);
q = fullfile(tmp, 'queue.txt');
fid = fopen(q, 'w');
for n = QS
  p = builtin('randperm', n);
  fprintf(fid, '%d', n); if n, fprintf(fid, ' %d', p); end; fprintf(fid, '\n');
end
fclose(fid);
qu = struct('sizes', QS, 'qtext', fileread(q));
randperm_config(q, lg);
qu.out = arrayfun(@(n) randperm(n), QS, 'UniformOutput', false);
qu.logtext = fileread(lg);
randperm_config(q);
randperm(4); randperm(0);
randperm_config(q);            % rewind
qu.rew = {randperm(4), randperm(0)};
q2 = fullfile(tmp, 'queue2.txt');
fid = fopen(q2, 'w'); fprintf(fid, '3 3 1 2\n'); fclose(fid);
randperm_config(q);
randperm(4);
setenv('FD_RANDPERM', q2);     % a different file reloads without randperm_config
qu.sw = randperm(3);
out.qu = qu;

% --- er: errors -----------------------------------------------------------------------
er = struct();
fid = fopen(q2, 'w'); fprintf(fid, '2 2 1\n'); fclose(fid);
randperm_config(q2); randperm(2);
er.exhausted = errmsg(@() randperm(2));
randperm_config(q2);
er.length = errmsg(@() randperm(3));
fid = fopen(q2, 'w'); fprintf(fid, '3 1 1 2\n'); fclose(fid);
randperm_config(q2);
er.notperm = errmsg(@() randperm(3));
fid = fopen(q2, 'w'); fprintf(fid, '3 1 2\n'); fclose(fid);
randperm_config(q2);
er.header = errmsg(@() randperm(3));
randperm_config('identity');
er.twoarg_identity = errmsg(@() randperm(5, 2));
randperm_config(q);
er.twoarg_queue = errmsg(@() randperm(5, 2));
randperm_config();
rand('state', 1);
er.twoarg_builtin = randperm(5, 2);   % passes through
out.er = er;

% --- cs: choose_seedpairs call site ---------------------------------------------------
graph = struct('z', [1 1 1 1 1 1 1 2 2]);
cs = struct('z', graph.z, 'c', 1);
randperm_config('identity');
cs.ident = choose_seedpairs(graph, -1, 1, 1, struct());
randperm_config('', lg);
rand('state', 3);
cs.rec = choose_seedpairs(graph, -1, 1, 1, struct());
cs.reclog = fileread(lg);
randperm_config(lg);
cs.rep = choose_seedpairs(graph, -1, 1, 1, struct());
out.cs = cs;

randperm_config();
rmpath(sdir);
confirm_recursive_rmdir(false); rmdir(tmp, 's');
save('-v7', outfile, '-struct', 'out');


function m = errmsg(f)
m = '';
try
  f();
catch e
  m = e.message;
end
