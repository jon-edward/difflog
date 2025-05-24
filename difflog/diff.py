"""
The diffing mechanism for API members.
"""

import ast
from dataclasses import dataclass
from deepdiff import DeepDiff, Delta
import logging

from parse_api import ModuleMember, ApiMember
from typing import Any

__all__ = (
    "diff",
    "ApiChange",
    "Added",
    "Removed",
    "TypeChanged",
    "Modified",
    "AddedClassBase",
    "RemovedClassBase",
    "ModifiedClassBase",
    "AddedDecorator",
    "RemovedDecorator",
    "ModifiedDecorator",
)


@dataclass(frozen=True, order=True)
class ApiChange:
    """
    Base class for API changes.
    """

    path: str
    name: str

    def _prefix(self, message: str) -> str:
        prefix = f'[{self.path}] ' if self.path else ''
        return f"{prefix}{message}"

    def describe(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True, order=True)
class Added(ApiChange):
    """
    Added API member.
    """

    type_name: str

    def describe(self) -> str:
        return self._prefix(f"Added `{self.name}`")


@dataclass(frozen=True, order=True)
class Removed(ApiChange):
    """
    Removed API member.
    """

    type_name: str

    def describe(self) -> str:
        return self._prefix(f"Removed {self.type_name} `{self.name}`")


@dataclass(frozen=True, order=True)
class TypeChanged(ApiChange):
    """
    API member's type changed.
    """

    from_type: str
    to_type: str

    def describe(self) -> str:
        return self._prefix(f"Changed type of `{self.name}` from {self.from_type} to {self.to_type}")


@dataclass(frozen=True, order=True)
class Modified(ApiChange):
    """
    Some property of the API member changed.
    """

    type_name: str
    prop: str
    from_value: Any
    to_value: Any

    def describe(self) -> str:
        return self._prefix(f"Changed {self.type_name} `{self.name}` {self.prop} from {'nothing' if self.from_value == '' else self.from_value} to {self.to_value}")


@dataclass(frozen=True, order=True)
class AddedClassBase(ApiChange):
    """
    Added base class to a class.
    """

    value: str
    position: int

    def describe(self) -> str: 
        return self._prefix(f"Added base class {self.value} to `{self.name}` at position {self.position}")


@dataclass(frozen=True, order=True)
class RemovedClassBase(ApiChange):
    """
    Removed base class from a class.
    """

    value: str
    position: int

    def describe(self) -> str:
        return self._prefix(f"Removed base class {self.value} from `{self.name}` at position {self.position}")


@dataclass(frozen=True, order=True)
class ModifiedClassBase(ApiChange):
    """
    Modified base class of a class.
    """

    position: int
    from_value: str
    to_value: str

    def describe(self) -> str:
        return self._prefix(f"Modified base class of `{self.name}` at position {self.position} from {self.from_value} to {self.to_value}")


@dataclass(frozen=True, order=True)
class AddedDecorator(ApiChange):
    """
    Added decorator to a function or class.
    """

    type_name: str
    value: str
    position: int

    def describe(self) -> str:
        return self._prefix(f"Added decorator {self.value} to {self.type_name} `{self.name}` at position {self.position}")


@dataclass(frozen=True, order=True)
class RemovedDecorator(ApiChange):
    """
    Removed decorator from a function or class.
    """

    type_name: str
    value: str
    position: int

    def describe(self) -> str:
        return self._prefix(f"Removed decorator {self.value} from {self.type_name} `{self.name}` at position {self.position}")


@dataclass(frozen=True, order=True)
class ModifiedDecorator(ApiChange):
    """
    Modified decorator of a function or class.
    """

    type_name: str
    position: int
    from_value: str
    to_value: str

    def describe(self) -> str:
        return self._prefix(f"Modified decorator of {self.type_name} `{self.name}` at position {self.position} from {self.from_value} to {self.to_value}")


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
        elif row.action == "values_changed" and row.path[-1] == "members" and isinstance(row.value, dict):
            # There are no common members between a member of the old and new module, remove all old and add all new.
            for member in row.old_value.values(): # type: ignore
                output.append(
                    Removed(
                        path=".".join(member.path[:-1]),
                        name=member.path[-1],
                        type_name=member.type_name,
                    )
                )
            for member in row.value.values():
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
                    position=row.path[-1],  # type: ignore
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
                    position=row.path[-1],  # type: ignore
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
                    position=row.path[-1],  # type: ignore
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
                    position=row.path[-1],  # type: ignore
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
                    position=row.path[-1],  # type: ignore
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
                    position=row.path[-1],  # type: ignore
                )
            )
        else:
            logging.error(f"Unknown change: {row}")

    return output
