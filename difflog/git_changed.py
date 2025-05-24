
import subprocess
from typing import Tuple

_GIT_AVAILABLE = False
try:
    subprocess.check_output(["git", "--version"])
    _GIT_AVAILABLE = True
except Exception:
    pass

class GitError(Exception):
    pass

def git_file_content(hash: str, path: str):
    if not _GIT_AVAILABLE: raise GitError("git is not available")
    return subprocess.check_output(["git", "show", f"{hash}:{path}"]).decode("utf-8")


if __name__ == "__main__":
    print(git_file_content("HEAD", "difflog/diff.py"))

