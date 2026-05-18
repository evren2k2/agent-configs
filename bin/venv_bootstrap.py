"""venv_bootstrap — run the vault tooling under a Python that has the
semantic-search dependencies (sentence-transformers, numpy).

ensure_venv() resolves an interpreter in priority order:

  1. the shell's current Python (the interpreter already running)
  2. the agent-configs repo venv   <repo>/.venv
  3. the global user venv          ~/.venv

The first interpreter that can import the required packages wins; if it is not
the one already running, the process is relaunched under it. If none qualifies,
ensure_venv() returns quietly: the core `vault` CLI and the graph MCP tools do
not need these packages — only `vault embed` and vault_semantic_search do, and
those print an actionable install message pointing at requirements.txt.

Why this matters: a venv auto-activates only in interactive shells. The MCP
server and the 5-min sync cron are launched *non-interactively* and would
otherwise run under a system Python that lacks the packages. The cascade is what
makes those contexts work.

subprocess (not os.execv) is used for the relaunch: on Windows os.execv detaches
the child, so a parent — cron, the MCP host — would see the launcher exit before
the work finished. stdin/stdout/stderr are inherited, so MCP stdio flows through.

Stdlib only — must import cleanly under any interpreter.
"""

import os
import sys

_GUARD = "VAULT_VENV_BOOTSTRAPPED"

# Import names (not pip names) of the semantic-search dependencies.
_REQUIRED = ("sentence_transformers", "numpy")


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _venv_python(venv_dir):
    """Interpreter path inside a venv directory, or None if it is absent."""
    if not os.path.isdir(venv_dir):
        return None
    cand = (os.path.join(venv_dir, "Scripts", "python.exe") if os.name == "nt"
            else os.path.join(venv_dir, "bin", "python"))
    return cand if os.path.isfile(cand) else None


def _same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def _deps_present():
    """True if the *current* interpreter can import every required package.
    find_spec locates packages without importing them — torch is not loaded
    just to answer the question."""
    import importlib.util
    try:
        return all(importlib.util.find_spec(m) is not None for m in _REQUIRED)
    except Exception:
        return False


def _deps_present_in(python):
    """True if a *different* interpreter has the required packages. Probed in a
    subprocess (find_spec, so nothing heavy loads) — used to verify a venv
    before relaunching into it, so the cascade can fall through cleanly."""
    import subprocess
    probe = (
        "import importlib.util as u, sys; "
        "sys.exit(0 if all(u.find_spec(m) for m in %r) else 1)" % (_REQUIRED,)
    )
    try:
        return subprocess.run(
            [python, "-c", probe],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
    except OSError:
        return False


def ensure_venv():
    """Relaunch under the first interpreter in the cascade (current Python ->
    <repo>/.venv -> ~/.venv) that has the semantic-search deps. No-op when the
    current interpreter already qualifies, or when none does."""
    if os.environ.get(_GUARD) == "1":
        return
    # 1. The shell's current Python — already running; no relaunch if it works.
    if _deps_present():
        return
    # 2. the repo venv, then 3. the global venv.
    for venv_dir in (os.path.join(_repo_root(), ".venv"),
                     os.path.join(os.path.expanduser("~"), ".venv")):
        py = _venv_python(venv_dir)
        if not py or _same_file(py, sys.executable):
            continue
        if not _deps_present_in(py):
            continue
        import subprocess
        env = dict(os.environ, **{_GUARD: "1"})
        try:
            proc = subprocess.run([py, *sys.argv], env=env)
        except OSError:
            continue  # cannot spawn — try the next candidate
        sys.exit(proc.returncode)
    # 4. No interpreter qualified. Return quietly; `vault embed` and
    #    vault_semantic_search surface an actionable install message.
    return
