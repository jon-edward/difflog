# Difflog

**Automated Changelog Generation via API Diffing for Python Projects**

Difflog simplifies the task of generating changelogs by using static analysis to detect API-level changes in Python scripts. It outputs a concise Markdown changelog, ideal for release notes or CI/CD workflows.

Example integration: See [.github/workflows/changes.yml](.github/workflows/changes.yml)

---

## Installation

Install Difflog via pip:

```bash
pip install difflog
```

---

## Detecting API Changes Between Files

Given two versions of a Python script:

**`main1.py`**

```python
def main():
    print("Hello, world!")

if __name__ == "__main__":
    main()
```

**`main2.py`**

```python
def main(name: str):
    print("Hello, world! My name is", name)

if __name__ == "__main__":
    main("John")
    print("Goodbye, world!")
```

Run the following command to detect API differences:

```bash
python -m difflog main1.py main2.py
```

**Example output:**

```
[main] Added positional or keyword argument `name`
```

For more examples, see [tests/test_api_diffing.py](tests/test_api_diffing.py)

---

## Generating a Markdown Changelog from Git

If you're working in a Git repository, you can generate a changelog based on file-level API changes between commits:

```bash
difflog.git_report > CHANGES.md
```

This will:

- Analyze code changes since the last Git push
- Output a changelog in GitHub's Markdown format to `CHANGES.md`

You can also specify a revision range:

```bash
difflog.git_report --from-rev v1.0.0 --to-rev HEAD > CHANGES.md
```

---

## Programmatic API Usage

Use Difflog as a Python module for custom workflows, e.g., filtering changes, customizing output formats, etc.

```python
import difflog

with open("old_file.py") as f:
    old_code = f.read()

with open("new_file.py") as f:
    new_code = f.read()

for change in difflog.diff(old_code, new_code):
    print(change)
```

---

## Contributing

Contributions are welcome!
To contribute:

1. Fork the repository
2. Create a new branch
3. Submit a pull request

See existing issues or open a new one to discuss your ideas.

---

## License

Licensed under the **Apache License 2.0**.
See [LICENSE](LICENSE) for details.

---

## Acknowledgments

Difflog leverages the excellent [DeepDiff](https://pypi.org/project/deepdiff/) library for structural diffing.
