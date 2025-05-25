"""
Utilities for reporting API changes to GitHub.
"""

import argparse
from fnmatch import fnmatch
import pathlib
import subprocess
from typing import Callable

from difflog.diff import ApiChange, diff

__all__ = ("git_report", "md_report")


def _check_in_git_repo():
    try:
        subprocess.check_output(["git", "rev-parse"], stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        raise RuntimeError("not in git repo")


def _diff_content(changes: list[ApiChange]) -> str:
    return "\n".join(
        sorted([change._diff_symbol + " " + change.describe() for change in changes])
    )


def md_report(changes: list[ApiChange] | dict[str, list[ApiChange]]) -> str:
    """
    Generate a Markdown report of API changes.
    """
    total_content = ""
    if isinstance(changes, dict):
        for name, changes in sorted(changes.items(), key=lambda x: x[0]):
            content = _diff_content(changes).strip()
            if not content:
                continue
            total_content += f"@@ {name} @@\n{content}\n\n"
        diff_element = f"```diff\n{'# No changes' if not total_content.strip() else total_content.strip()}\n```"
        return diff_element
    total_content = _diff_content(changes).strip()
    return f"```diff\n{'# No changes' if not total_content else total_content}\n```"


def _git_changed_files(
    from_rev: str | None = None, to_rev: str | None = None
) -> tuple[str, str | None, list[str]]:
    """
    Returns a tuple of (from_rev, to_rev, changed_files)
    If from_rev is not None, returns the files changed since the given hash.
    Else, returns the files changed since the last push.
    """

    _check_in_git_repo()

    if from_rev is None:
        # Get upstream revision if from_rev is not provided
        from_rev = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()

    p = f"{from_rev}..{to_rev}" if to_rev is not None else from_rev
    output = subprocess.check_output(
        ["git", "diff", "--name-only", p, "--", "*.py"],
        text=True,
    ).strip()

    return (
        from_rev,
        to_rev,
        [line.strip() for line in output.splitlines() if line.strip()],
    )


def _git_content_from_file(file_path: str, rev: str | None) -> str:
    _check_in_git_repo()

    try:
        if rev is None:
            # If rev is not provided, read the file from disk
            return pathlib.Path(file_path).read_text()
        return subprocess.check_output(
            ["git", "show", f"{rev}:{file_path}"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def git_report(
    from_rev: str | None = None,
    to_rev: str | None = None,
    include_files: Callable[[str], bool] = lambda x: True,
) -> str:
    from_rev, to_rev, changed_files = _git_changed_files(from_rev, to_rev)
    return "## API Changes\n" + md_report(
        {
            file_path: diff(
                _git_content_from_file(file_path, from_rev),
                _git_content_from_file(file_path, to_rev),
            )
            for file_path in changed_files
            if include_files(file_path)
        }
    )


def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="Generate a Markdown report of API changes in a git repository."
    )
    parser.add_argument(
        "--from-rev",
        "--from",
        type=str,
        default=None,
        help="The revision to compare from (default: last push).",
    )
    parser.add_argument(
        "--to-rev",
        "--to",
        type=str,
        default=None,
        help="The revision to compare to (default: working directory).",
    )
    parser.add_argument(
        "--files",
        "-f",
        type=str,
        default="*.py",
        help="The files to compare (default: *.py)",
    )

    args_dict = vars(parser.parse_args(args))

    print(
        git_report(
            args_dict["from_rev"],
            args_dict["to_rev"],
            lambda x: fnmatch(x, args_dict["files"]),
        )
    )


if __name__ == "__main__":
    main()
