"""
The diffing mechanism for API members.
"""

import ast
from dataclasses import dataclass
from deepdiff import DeepDiff, Delta
import logging

from api_members import ModuleMember, ApiMember
from typing import Any


@dataclass
class ApiChange:
    """
    Base class for API changes.
    """
    path: str
    name: str


@dataclass
class Added(ApiChange):
    """
    Added API member.
    """
    type_name: str


@dataclass
class Removed(ApiChange):
    """
    Removed API member.
    """
    type_name: str


@dataclass
class TypeChanged(ApiChange):
    """
    API member's type changed.
    """
    from_type: str
    to_type: str


@dataclass
class Modified(ApiChange):
    """
    Some property of the API member changed.
    """
    type_name: str
    prop: str
    from_value: Any
    to_value: Any


@dataclass
class AddedClassBase(ApiChange):
    """
    Added base class to a class.
    """
    value: str
    position: int


@dataclass
class RemovedClassBase(ApiChange):
    """
    Removed base class from a class.
    """
    value: str
    position: int


@dataclass
class ModifiedClassBase(ApiChange):
    """
    Modified base class of a class.
    """
    position: int
    from_value: str
    to_value: str


@dataclass
class AddedDecorator(ApiChange):
    """
    Added decorator to a function or class.
    """
    type_name: str
    value: str
    position: int


@dataclass
class RemovedDecorator(ApiChange):
    """
    Removed decorator from a function or class.
    """
    type_name: str
    value: str
    position: int


@dataclass
class ModifiedDecorator(ApiChange):
    """
    Modified decorator of a function or class.
    """
    type_name: str
    position: int
    from_value: str
    to_value: str


def _get_member_from_path(module: ModuleMember, path: list[str]) -> ApiMember:
    """
    Get the last member from a path. This is essentially a single linked list traversal.
    """
    last_member = module
    for name in path:
        module = module[name]
        if isinstance(module, ApiMember):
            last_member = module
    return last_member


def diff(
    old_module: ModuleMember | ast.Module | str,
    new_module: ModuleMember | ast.Module | str,
) -> list[ApiChange]:
    """
    List the API changes between two modules.

    Args:
        old_module: The old module.
        new_module: The new module.

    Returns:
        A list of changes.
    """
    if isinstance(old_module, str):
        old_module = ModuleMember(node=ast.parse(old_module))
    elif isinstance(old_module, ast.Module):
        old_module = ModuleMember(node=old_module)
    if isinstance(new_module, str):
        new_module = ModuleMember(node=ast.parse(new_module))
    elif isinstance(new_module, ast.Module):
        new_module = ModuleMember(node=new_module)

    output = []

    for row in Delta(
        DeepDiff(old_module, new_module, exclude_regex_paths=r".*\.(?:node|path)"),
        bidirectional=True,
    ).to_flat_rows():
        if row.action == "dictionary_item_added" and isinstance(row.value, ApiMember):
            output.append(
                Added(
                    path=".".join(row.value.path[:-1]),
                    name=row.value.path[-1],
                    type_name=row.value.type_name,
                )
            )
        elif row.action == "dictionary_item_removed" and isinstance(
            row.value, ApiMember
        ):
            output.append(
                Removed(
                    path=".".join(row.value.path[:-1]),
                    name=row.value.path[-1],
                    type_name=row.value.type_name,
                )
            )
        elif row.action == "type_changes" and isinstance(row.value, ApiMember):
            output.append(
                TypeChanged(
                    path=".".join(row.value.path[:-1]),
                    name=row.value.path[-1],
                    from_type=row.old_value.type_name,  # type: ignore
                    to_type=row.value.type_name,
                )
            )
        elif row.action == "values_changed" and len(row.path) == 1:
            # There are no common API members between the old and new modules, so
            # all old members are removed and all new members are added.
            for member in old_module.members.values():
                output.append(
                    Removed(
                        path=".".join(member.path[:-1]),
                        name=member.path[-1],
                        type_name=member.type_name,
                    )
                )
            for member in new_module.members.values():
                output.append(
                    Added(
                        path=".".join(member.path[:-1]),
                        name=member.path[-1],
                        type_name=member.type_name,
                    )
                )
        elif (
            row.action == "values_changed"
            and len(row.path) > 1
            and row.path[-2] == "bases"
        ):
            obj = _get_member_from_path(old_module, row.path[:-1])
            output.append(
                ModifiedClassBase(
                    path=".".join(obj.path[:-1]),
                    name=obj.path[-1],
                    position=row.path[-1],
                    from_value=row.old_value,  # type: ignore
                    to_value=row.value,  # type: ignore
                )
            )
        elif (
            row.action == "values_changed"
            and len(row.path) > 1
            and row.path[-2] == "decorators"
        ):
            obj = _get_member_from_path(old_module, row.path[:-1])
            output.append(
                ModifiedDecorator(
                    path=".".join(obj.path[:-1]),
                    name=obj.path[-1],
                    type_name=obj.type_name,
                    position=row.path[-1],
                    from_value=row.old_value,  # type: ignore
                    to_value=row.value,  # type: ignore
                )
            )
        elif row.action == "values_changed" and len(row.path) > 1:
            obj = _get_member_from_path(old_module, row.path[:-1])
            output.append(
                Modified(
                    path=".".join(obj.path[:-1]),
                    name=obj.path[-1],
                    type_name=obj.type_name,
                    prop=row.path[-1],
                    from_value=row.old_value,
                    to_value=row.value,
                )
            )
        elif (
            row.action == "iterable_item_added"
            and len(row.path) > 1
            and row.path[-2] == "decorators"
        ):
            obj = _get_member_from_path(old_module, row.path[:-1])
            output.append(
                AddedDecorator(
                    path=".".join(obj.path[:-1]),
                    name=obj.path[-1],
                    type_name=obj.type_name,
                    value=row.value,  # type: ignore
                    position=row.path[-1],
                )
            )
        elif (
            row.action == "iterable_item_removed"
            and len(row.path) > 1
            and row.path[-2] == "decorators"
        ):
            obj = _get_member_from_path(old_module, row.path[:-1])
            output.append(
                RemovedDecorator(
                    path=".".join(obj.path[:-1]),
                    name=obj.path[-1],
                    type_name=obj.type_name,
                    value=row.value,  # type: ignore
                    position=row.path[-1],
                )
            )
        elif (
            row.action == "iterable_item_added"
            and len(row.path) > 1
            and row.path[-2] == "bases"
        ):
            obj = _get_member_from_path(old_module, row.path[:-1])
            output.append(
                AddedClassBase(
                    path=".".join(obj.path[:-1]),
                    name=obj.path[-1],
                    value=row.value,  # type: ignore
                    position=row.path[-1],
                )
            )
        elif (
            row.action == "iterable_item_removed"
            and len(row.path) > 1
            and row.path[-2] == "bases"
        ):
            obj = _get_member_from_path(old_module, row.path[:-1])
            output.append(
                RemovedClassBase(
                    path=".".join(obj.path[:-1]),
                    name=obj.path[-1],
                    value=row.value,  # type: ignore
                    position=row.path[-1],
                )
            )
        else:
            logging.error(f"Unknown change: {row}")

    return output


if __name__ == "__main__":
    import ast

    script1 = """
node: int = 2
x: int = 2

@decorator1
@decorator2
def bar(a: int, b: int = 1, *args: int, **kwargs: int) -> str:
    return ""

class Foo(metaclass=1):
    def fun() -> str: pass
"""
    script2 = """
def x() -> str: pass

@decorator2
@decorator1
def bar(a: int, b: int = 2, *args: int, **kwargs: int) -> str:
    return ""

def foo(start, a: int, /, b: int = 1, *args: int, **kwargs: int) -> str:
    return ""

class Foo:
    def fun() -> int: pass
"""
    # from pprint import pprint
    from pathlib import Path

    for change in diff(
        ModuleMember(node=ast.parse(Path("io_old.py").read_text())),
        ModuleMember(node=ast.parse(Path("io_new.py").read_text())),
    ):
        print(change)
