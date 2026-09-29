function randperm_config(source, logfile)
% Configure the randperm shim (randperm.m in this directory) and rewind its queue.
%
% randperm_config()                 pass through to the built-in, no log
% randperm_config('identity')       randperm(n) = 1:n
% randperm_config(queuefile)        replay queuefile from its first line
% randperm_config(source, logfile)  also append every result to logfile (truncated here)
%
% Sets FD_RANDPERM / FD_RANDPERM_LOG and clears the shim's persistent state.
if nargin < 1, source = ''; end
if nargin < 2, logfile = ''; end
setenv('FD_RANDPERM', source);
setenv('FD_RANDPERM_LOG', logfile);
if ~isempty(logfile)
  fid = fopen(logfile, 'w');
  if fid < 0
    error('randperm_config: cannot open log file %s', logfile);
  end
  fclose(fid);
end
clear('randperm');
