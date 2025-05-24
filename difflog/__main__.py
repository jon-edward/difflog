import argparse
from pathlib import Path

from diff import diff


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("old_file", type=Path, help="The old Python file to compare.")
    parser.add_argument("new_file", type=Path, help="The new Python file to compare.")
    args = parser.parse_args()

    for change in sorted(diff(args.old_file.read_text(), args.new_file.read_text())):
        print(change.describe())

if __name__ == "__main__":
    main()
