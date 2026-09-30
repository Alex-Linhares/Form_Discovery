#!/usr/bin/env python3
"""Ralph Loop runner (see ../ralph_loop_guide.md). Copy this file into each loopNNNN folder.

Each iteration:
  1. reads TASK.md + PROGRESS.md, picks the first `[ ]` item in iterations.md
  2. spawns a fresh `claude -p` session with the combined prompt (no session continuation)
  3. runs the regression gate (TEST_CMD) after Claude finishes
  4. passes  -> commits everything
     fails   -> asks Claude to fix (up to MAX_FIX_ATTEMPTS), then reverts code but keeps
                PROGRESS.md / iterations.md findings, and commits those
  5. stops when PROGRESS.md contains the sentinel LOOP_COMPLETE or no `[ ]` items remain

Usage (from this folder):
  python3 loop.py                 # 10 iterations, resume
  python3 loop.py 60              # 60 iterations
  python3 loop.py 60 --fresh      # reset PROGRESS.md first
  python3 loop.py 20 TASK.md PROGRESS.md
  python3 loop.py 1 --dry-run     # print the prompt, do not call claude

Environment overrides:
  RALPH_CLAUDE_ARGS   extra args for `claude -p`
                      (default: --dangerously-skip-permissions, required for unattended runs)
  RALPH_TEST_CMD      regression command (default: python -m pytest -q -m "not slow")
  RALPH_TIMEOUT_MIN   per-Claude-call timeout in minutes (default 240; a hang guard, not a budget)
"""
from __future__ import annotations

import datetime as _dt
import functools
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
REPO_ROOT = LOOP_DIR.parents[1]
SENTINEL = "LOOP_COMPLETE"
LOOP_ID = LOOP_DIR.name  # e.g. loop0002
MAX_FIX_ATTEMPTS = 3
CLAUDE_ARGS = shlex.split(os.environ.get("RALPH_CLAUDE_ARGS", "--dangerously-skip-permissions"))
TEST_CMD = os.environ.get("RALPH_TEST_CMD", 'python -m pytest -q -m "not slow"')
TIMEOUT_S = int(float(os.environ.get("RALPH_TIMEOUT_MIN", "240")) * 60)
PYTEST_NO_TESTS_COLLECTED = 5
print = functools.partial(print, flush=True)  # keep log ordered when redirected

ITEM_RE = re.compile(r"^- \[( |x|~)\] (\d+[a-z]?)\.", re.M)  # allows inserted items like 03b


def sh(cmd: list[str] | str, *, cwd: Path = REPO_ROOT, check=False, capture=True, timeout=None,
       input_text: str | None = None) -> subprocess.CompletedProcess:
    if isinstance(cmd, str):
        cmd = ["bash", "-lc", cmd]
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, timeout=timeout,
                          input=input_text,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.STDOUT if capture else None)


def now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def has_sentinel(progress_text: str) -> bool:
    """True only if LOOP_COMPLETE stands alone on a line.

    A plain substring test matched the sentinel quoted inside an item description that a
    session had copied into PROGRESS.md (iteration 37), which ended the loop early.
    """
    return re.search(rf"^\s*{SENTINEL}\s*$", progress_text, re.M) is not None


def next_item(iterations_text: str) -> tuple[str, str] | None:
    """Return (number, full item text) of the first `[ ]` item, or None."""
    matches = list(ITEM_RE.finditer(iterations_text))
    for k, m in enumerate(matches):
        if m.group(1) == " ":
            start = m.start()
            end = matches[k + 1].start() if k + 1 < len(matches) else len(iterations_text)
            block = iterations_text[start:end]
            block = re.split(r"\n## ", block)[0].rstrip()  # stop at next section header
            return m.group(2), block
    return None


def counts(iterations_text: str) -> tuple[int, int, int]:
    states = [m.group(1) for m in ITEM_RE.finditer(iterations_text)]
    return states.count("x"), states.count("~"), states.count(" ")


def tail_progress(text: str, max_iterations: int = 4) -> str:
    """Keep the status header plus the last few iteration sections to bound prompt size."""
    parts = re.split(r"(?m)^(?=## Iteration )", text)
    if len(parts) <= max_iterations + 1:
        return text
    return parts[0] + f"[... {len(parts) - 1 - max_iterations} earlier iterations omitted ...]\n\n" \
        + "".join(parts[-max_iterations:])


def build_prompt(task: str, progress: str, iterations: str, item_no: str, item: str, iteration_n: int) -> str:
    return f"""You are one iteration of a Ralph Loop (fresh-context pattern). Repo root: {REPO_ROOT}
Loop folder: {LOOP_DIR}. Read /PLAN.md sections relevant to the item before starting.

Rules:
- Work on exactly ONE item: item {item_no} below. Do not start any other item.
- When the item is solved, change its checkbox in {LOOP_DIR/'iterations.md'} from `[ ]` to `[x]`;
  if blocked after a genuine attempt, mark it `[~]` and document the blocker.
- Append a section to {LOOP_DIR/'PROGRESS.md'} in this exact shape:
    ## Iteration {iteration_n} — {now()}
    ### Completed
    ### Blockers
    ### Next
  and update the `**Current**: N/M SOLVED` line in its status header.
- Long commands: a single tool call is capped at 10 minutes, and a session cannot wait
  longer than that in one call. For anything longer (the full gate, fixture regeneration),
  start it in the background writing to a log file, then WAIT IN THE FOREGROUND with
  repeated short waits, e.g. `timeout 540 tail --pid=<PID> -f /dev/null` or a
  `until grep -q ... ; do sleep 15; done` loop under `timeout 540`, re-issued until the job
  is finished. NEVER end your turn while the job is still running: the session ends when
  you stop, and the runner then commits whatever is on disk without your checkbox update or
  PROGRESS.md entry (this happened on loop0001 items 15 and 19 and loop0002 item 02, costing
  an extra iteration each time). If you truly cannot finish, write the PROGRESS.md entry and
  leave the checkbox unticked before stopping.
- Do NOT git commit; the loop script commits after running the regression gate:
    {TEST_CMD}
  Make sure that command passes before you finish (exit code 5 = no tests yet is acceptable
  only during Phase 0).
- If every item in iterations.md is `[x]` or `[~]` and you have verified them, add the exact
  line `{SENTINEL}` at the end of PROGRESS.md. Never add it otherwise.

=================== TASK.md ===================
{task}

=================== PROGRESS.md (recent) ===================
{tail_progress(progress)}

=================== iterations.md (status) ===================
{iterations}

=================== YOUR ITEM ===================
{item}
"""


def run_claude(prompt: str, *, dry_run: bool) -> int:
    if dry_run:
        print(prompt)
        return 0
    cmd = ["claude", "-p", *CLAUDE_ARGS]
    print(f"[loop] running: {' '.join(shlex.quote(c) for c in cmd)}  (prompt via stdin, {len(prompt)} chars)")
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, input=prompt, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"[loop] claude timed out after {TIMEOUT_S//60} min")
        return 124
    return proc.returncode


def run_tests() -> tuple[bool, str]:
    print(f"[loop] regression gate: {TEST_CMD}")
    proc = sh(TEST_CMD, timeout=TIMEOUT_S)
    ok = proc.returncode in (0, PYTEST_NO_TESTS_COLLECTED)
    out = proc.stdout or ""
    print(out[-4000:])
    return ok, out


def git_has_changes() -> bool:
    return bool(sh(["git", "status", "--porcelain"]).stdout.strip())


def git_commit(message: str) -> None:
    if not git_has_changes():
        print("[loop] nothing to commit")
        return
    sh(["git", "add", "-A"])
    proc = sh(["git", "commit", "-q", "-m", message])
    print(proc.stdout.strip() or f"[loop] committed: {message.splitlines()[0]}")


def revert_keep_findings(progress_path: Path, iterations_path: Path, reason: str) -> None:
    """Revert all code changes but keep PROGRESS.md / iterations.md, annotated with the reason."""
    progress_text = progress_path.read_text()
    iterations_text = iterations_path.read_text()
    sh(["git", "reset", "-q", "--hard"])
    sh(["git", "clean", "-fdq", "-e", str(LOOP_DIR.relative_to(REPO_ROOT))])
    note = (f"\n> **Reverted by loop.py at {now()}**: {reason}. Code changes were discarded; "
            f"the notes above are kept for the next iteration.\n")
    progress_path.write_text(progress_text.rstrip() + "\n" + note)
    # keep iterations.md edits too, but a reverted item cannot count as solved
    iterations_path.write_text(iterations_text)


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    n_iter = int(args[0]) if args else 10
    task_path = Path(args[1]) if len(args) > 1 else LOOP_DIR / "TASK.md"
    progress_path = Path(args[2]) if len(args) > 2 else LOOP_DIR / "PROGRESS.md"
    iterations_path = LOOP_DIR / "iterations.md"
    if not iterations_path.exists():
        iterations_path = LOOP_DIR / "near_misses.md"  # backward compatibility
    dry_run = "--dry-run" in flags

    if "--fresh" in flags:
        loop_id = LOOP_DIR.name.replace("loop", "")
        total = sum(counts(iterations_path.read_text()))
        progress_path.write_text(
            f"# Progress Log\n\n## Ralph Loop {loop_id} Status\n- **Started**: {_dt.date.today()}\n"
            f"- **Target**: {total} items (see iterations.md)\n- **Current**: 0/{total} SOLVED\n\n---\n")
        text = iterations_path.read_text()
        iterations_path.write_text(re.sub(r"^- \[(x|~)\]", "- [ ]", text, flags=re.M))
        print("[loop] fresh start: PROGRESS.md reset, all items unchecked")

    if not dry_run and sh(["git", "rev-parse", "--is-inside-work-tree"]).returncode != 0:
        print(f"[loop] {REPO_ROOT} is not a git repository; run `git init` first")
        return 2

    for i in range(1, n_iter + 1):
        task = task_path.read_text()
        progress = progress_path.read_text()
        iterations = iterations_path.read_text()
        if has_sentinel(progress):
            print(f"[loop] {SENTINEL} found; done")
            return 0
        item = next_item(iterations)
        solved, blocked, pending = counts(iterations)
        iteration_n = len(re.findall(r"(?m)^## Iteration ", progress)) + 1
        print(f"\n[loop] ===== iteration {iteration_n} ({i}/{n_iter}) — solved {solved}, blocked {blocked}, pending {pending} =====")
        if item is None:
            print("[loop] no pending items; asking Claude to verify and add the sentinel")
            item_no, item_text = "verify", "All items are marked done. Verify the acceptance criteria hold " \
                                          f"(run the regression gate), then add {SENTINEL} to PROGRESS.md."
        else:
            item_no, item_text = item
            print(f"[loop] item {item_no}: {item_text.splitlines()[0][:100]}")

        rc = run_claude(build_prompt(task, progress, iterations, item_no, item_text, iteration_n), dry_run=dry_run)
        if dry_run:
            return 0
        if rc != 0:
            print(f"[loop] claude exited with {rc}")

        ok, out = run_tests()
        attempt = 0
        while not ok and attempt < MAX_FIX_ATTEMPTS:
            attempt += 1
            print(f"[loop] regression gate failed; fix attempt {attempt}/{MAX_FIX_ATTEMPTS}")
            fix_prompt = (f"The regression gate `{TEST_CMD}` fails after your work on item {item_no} in "
                          f"{iterations_path}. Fix the failures without starting any other item, keep the "
                          f"tests honest (no skipping/xfailing to pass), and update PROGRESS.md. Output:\n\n"
                          f"{out[-15000:]}")
            run_claude(fix_prompt, dry_run=False)
            ok, out = run_tests()

        if ok:
            git_commit(f"{LOOP_ID} iteration {iteration_n}: item {item_no}\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>")
        else:
            revert_keep_findings(progress_path, iterations_path,
                                 f"regression gate still failing after {MAX_FIX_ATTEMPTS} fix attempts")
            git_commit(f"{LOOP_ID} iteration {iteration_n}: item {item_no} reverted (tests failing), notes kept\n\n"
                       f"Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>")

        if has_sentinel(progress_path.read_text()):
            print(f"[loop] {SENTINEL} found; done")
            return 0
    print("[loop] iteration budget exhausted")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
