function p = randperm(varargin)
% Test shim that shadows Octave's built-in randperm (PLAN.md §4.2, item 22).
%
% formdiscovery1.0 draws all of its randomness from randperm(n) (choose_seedpairs.m:24,
% best_split.m:35, swapobjclust.m:33, spr.m:57/59, collapsedims.m:35). Put this
% directory on the path before legacy/matlab/formdiscovery1.0 to control those draws. The
% environment variable FD_RANDPERM picks the source:
%
%   unset or ''   pass through to builtin('randperm', ...): same stream as without the shim
%   'identity'    return 1:n
%   <file>        replay a queue file: each call takes the next line, which must hold
%                 "n p1 ... pn" (1-based permutation of 1:n; "0" is the empty permutation)
%
% If FD_RANDPERM_LOG names a file, every call appends its result to it in the same
% "n p1 ... pn" format, so a log recorded here can be replayed by the queue mode or by
% formdiscovery.rng.ReplayPermutations. Errors (queue exhausted, wrong length, not a
% permutation) name the 1-based call number. The queue and its cursor are cached in a
% persistent variable and reloaded when FD_RANDPERM changes; `clear randperm` (or
% randperm_config) rewinds it. Only randperm(n) is replayable; randperm(n, m) is
% passed through to the built-in and is an error in the identity and queue modes.

persistent qfile queue cursor ncalls
if isempty(ncalls)
  qfile = ''; queue = {}; cursor = 0; ncalls = 0;
end
src = getenv('FD_RANDPERM');
ncalls = ncalls + 1;

if isempty(src)
  p = builtin('randperm', varargin{:});
else
  if numel(varargin) ~= 1
    error('randperm shim: only randperm(n) can be replayed (call %d)', ncalls);
  end
  n = varargin{1};
  if strcmp(src, 'identity')
    p = 1:n;
  else
    if ~strcmp(src, qfile)
      queue = read_queue(src);
      qfile = src;
      cursor = 0;
    end
    cursor = cursor + 1;
    if cursor > numel(queue)
      error('randperm shim: queue exhausted at call %d (randperm(%d); %d entries in %s)', ...
            ncalls, n, numel(queue), src);
    end
    p = queue{cursor};
    if numel(p) ~= n
      error('randperm shim: call %d asked for randperm(%d) but queue entry %d has length %d', ...
            ncalls, n, cursor, numel(p));
    end
    if ~isequal(sort(p), 1:n)
      error('randperm shim: queue entry %d is not a permutation of 1:%d', cursor, n);
    end
  end
end

logfile = getenv('FD_RANDPERM_LOG');
if ~isempty(logfile)
  fid = fopen(logfile, 'a');
  if fid < 0
    error('randperm shim: cannot open log file %s', logfile);
  end
  fprintf(fid, '%d', numel(p));
  if ~isempty(p), fprintf(fid, ' %d', p); end
  fprintf(fid, '\n');
  fclose(fid);
end


function queue = read_queue(fname)
% Parse a queue file: one "n p1 ... pn" line per permutation (blank lines ignored).
fid = fopen(fname, 'r');
if fid < 0
  error('randperm shim: cannot open queue file %s', fname);
end
queue = {};
lineno = 0;
while true
  line = fgetl(fid);
  if ~ischar(line), break; end
  lineno = lineno + 1;
  v = sscanf(line, '%d')';
  if isempty(v), continue; end
  if numel(v) ~= v(1) + 1
    fclose(fid);
    error('randperm shim: %s line %d: header says %d entries, found %d', ...
          fname, lineno, v(1), numel(v) - 1);
  end
  queue{end+1} = double(v(2:end));
end
fclose(fid);
