import argparse
from pathlib import Path

from difflog.diff import diff


def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("old_file", type=Path, help="The old Python file to compare.")
    parser.add_argument("new_file", type=Path, help="The new Python file to compare.")
    args_ = parser.parse_args(args=args)

    for change in sorted(diff(args_.old_file.read_text(), args_.new_file.read_text())):
        print(change.describe())


if __name__ == "__main__":
    main()
