"""
The diffing mechanism for API members.
"""
from dataclasses import dataclass
import logging
from typing import Generator, Any

from deepdiff import DeepDiff, Delta

from members import Member, Argument, Namespace, FunctionMember, AttributeMember

@dataclass
class Change:
    """
    Base class for all changes.
    """

@dataclass
class Added(Change):
    value: Member | Argument

@dataclass
class Removed(Change):
    value: Member | Argument

@dataclass
class Modified(Change):
    old_obj: Member | Argument
    new_obj: Member | Argument
    descriptor: str
    old_value: Any
    new_value: Any

@dataclass
class DecoratorAdded(Change):
    old_parent: FunctionMember | Namespace
    new_parent: FunctionMember | Namespace
    decorator: str
    position: int

@dataclass
class DecoratorRemoved(Change):
    old_parent: FunctionMember | Namespace
    new_parent: FunctionMember | Namespace 
    decorator: str
    position: int

@dataclass
class DecoratorModified(Change):
    old_parent: FunctionMember | Namespace
    new_parent: FunctionMember | Namespace
    old_decorator: str
    new_decorator: str
    position: int

@dataclass
class AsyncModified(Change):
    old_parent: FunctionMember
    new_parent: FunctionMember
    old_is_async: bool
    new_is_async: bool

@dataclass
class ArgumentPositionModified(Change):
    old_parent: FunctionMember
    new_parent: FunctionMember
    old_position: int
    new_position: int

@dataclass 
class ReturnsModified(Change):
    old_parent: FunctionMember
    new_parent: FunctionMember
    old_returns: str
    new_returns: str

@dataclass
class NoAlikeClasses(Change):
    old_ns: Namespace
    new_ns: Namespace

@dataclass
class NoAlikeFunctions(Change):
    old_ns: Namespace
    new_ns: Namespace

@dataclass
class NoAlikeAttributes(Change):
    old_ns: Namespace
    new_ns: Namespace

@dataclass
class AnnotationModified(Change):
    old_parent: Member | Argument
    new_parent: Member | Argument
    old_annotation: str
    new_annotation: str

@dataclass
class AssignmentValueModified(Change):
    old_parent: AttributeMember
    new_parent: AttributeMember
    old_value: str
    new_value: str

@dataclass
class DefaultModified(Change):
    old_parent: Argument
    new_parent: Argument
    old_default: str
    new_default: str

def _get_from_ns(ns: Namespace, path: tuple[str]):
    for name in path:
        ns = ns[name]
    return ns

def diff(old_module: Namespace, new_module: Namespace) -> Generator[Change, None, None]:
    rows = Delta(DeepDiff(old_module, new_module, exclude_regex_paths=r".*\.(?:lineno|end_lineno|path)$"), bidirectional=True).to_flat_rows(report_type_changes=False)
    for row in rows:
        if row.action == "dictionary_item_added":
            yield Added(row.value)
        elif row.action == "dictionary_item_removed":
            yield Removed(row.value)
        elif row.action == "values_changed" and row.path == ["classes"]:
            yield NoAlikeClasses(old_module, new_module)
        elif row.action == "values_changed" and row.path == ["functions"]:
            yield NoAlikeFunctions(old_module, new_module)
        elif row.action == "values_changed" and row.path == ["attributes"]:
            yield NoAlikeAttributes(old_module, new_module)
        elif row.action == "values_changed" and row.path[-2] == "decorators":
            parent = row.path[:-2]
            old_terminal = _get_from_ns(old_module, parent)
            new_terminal = _get_from_ns(new_module, parent)
            yield DecoratorModified(old_terminal, new_terminal, row.old_value, row.value, row.path[-1])
        elif row.action == "values_changed" and row.path[-1] == "is_async":
            parent = row.path[:-1]
            old_terminal = _get_from_ns(old_module, parent)
            new_terminal = _get_from_ns(new_module, parent)
            yield AsyncModified(old_terminal, new_terminal, row.old_value, row.value)
        elif row.action == "values_changed" and row.path[-1] == "position":
            parent = row.path[:-1]
            old_terminal = _get_from_ns(old_module, parent)
            new_terminal = _get_from_ns(new_module, parent)
            yield ArgumentPositionModified(old_terminal, new_terminal, row.old_value, row.value)
        elif row.action == "values_changed" and row.path[-1] == "returns":
            parent = row.path[:-1]
            old_terminal = _get_from_ns(old_module, parent)
            new_terminal = _get_from_ns(new_module, parent)
            yield ReturnsModified(old_terminal, new_terminal, row.old_value, row.value)
        elif row.action == "values_changed" and row.path[-1] == "annotation":
            parent = row.path[:-1]
            old_terminal = _get_from_ns(old_module, parent)
            new_terminal = _get_from_ns(new_module, parent)
            yield AnnotationModified(old_terminal, new_terminal, row.old_value, row.value)
        elif row.action == "values_changed" and row.path[-1] == "value":
            parent = row.path[:-1]
            old_terminal = _get_from_ns(old_module, parent)
            new_terminal = _get_from_ns(new_module, parent)
            yield AssignmentValueModified(old_terminal, new_terminal, row.old_value, row.value)
        elif row.action == "values_changed" and row.path[-1] == "default":
            parent = row.path[:-1]
            old_terminal = _get_from_ns(old_module, parent)
            new_terminal = _get_from_ns(new_module, parent)
            yield DefaultModified(old_terminal, new_terminal, row.old_value, row.value)
        elif row.action == "values_changed":
            parent = row.path[:-1]
            old_terminal = _get_from_ns(old_module, parent)
            new_terminal = _get_from_ns(new_module, parent)
            yield Modified(old_terminal, new_terminal, row.path[-1], row.old_value, row.value)
        elif row.action == "iterable_item_added" and row.path[-2] == "decorators":
            parent = row.path[:-2]
            yield DecoratorAdded(_get_from_ns(old_module, parent), _get_from_ns(new_module, parent), row.value, row.path[-1])
        elif row.action == "iterable_item_removed" and row.path[-2] == "decorators":
            parent = row.path[:-2]
            yield DecoratorRemoved(_get_from_ns(old_module, parent), _get_from_ns(new_module, parent), row.value, row.path[-1])
        else:
            logging.error(row)


if __name__ == "__main__":
    import ast
    script1 = """
x: int = 2

def bar(a: int, b: int = 1, *args: int, **kwargs: int) -> str:
    return ""

def foo(start, a: int, /, b: int = 1, *args: int, **kwargs: int) -> str:
    return ""
    
"""
    script2 = """
x: float = 2.0

def bar(a: int, b: int = 2, *args: int, **kwargs: int) -> str:
    return ""

def foo(start, a: int, /, b: int = 1, *args: int, **kwargs: int) -> str:
    return ""

"""
    from pprint import pprint
    for change in diff(Namespace.from_ast(ast.parse(script1)), Namespace.from_ast(ast.parse(script2))):
        print(change)
