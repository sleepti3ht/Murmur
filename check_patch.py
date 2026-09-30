# check_patch.py — verifies which version of the adapter is actually imported.
import inspect

from murmur.adapters.git_hook import GitHookAdapter as G

src_diff_args = inspect.getsource(G._diff_args)
src_run_git = inspect.getsource(G._run_git)

print("state:", "PATCHED" if hasattr(G, "_parent_ref") else "NOT_PATCHED")
print("EMPTY_TREE in _diff_args:", "EMPTY_TREE" in src_diff_args)
print("stderr tail in _run_git:", "stderr_tail" in src_run_git)