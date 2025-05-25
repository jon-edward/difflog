"""
The diffing mechanism for API members.
"""

import ast
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from deepdiff import DeepDiff, Delta

from difflog.module_member import ModuleMember, ApiMember

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
    """Base class for API changes."""

    path: str
    name: str

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="#")

    def _prefix(self, message: str) -> str:
        return f"[{self.path}] {message}" if self.path else message

    def describe(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True, order=True)
class Added(ApiChange):
    """Added API member."""

    type_name: str

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="+")

    def describe(self) -> str:
        return self._prefix(f"Added {self.type_name} `{self.name}`")


@dataclass(frozen=True, order=True)
class Removed(ApiChange):
    """Removed API member."""

    type_name: str

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="-")

    def describe(self) -> str:
        return self._prefix(f"Removed {self.type_name} `{self.name}`")


@dataclass(frozen=True, order=True)
class TypeChanged(ApiChange):
    """API member's type changed."""

    from_type: str
    to_type: str

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="!")

    def describe(self) -> str:
        return self._prefix(
            f"Changed type of `{self.name}` from {self.from_type} to {self.to_type}"
        )


@dataclass(frozen=True, order=True)
class Modified(ApiChange):
    """Some property of the API member changed."""

    type_name: str
    prop: str
    from_value: Any
    to_value: Any

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="!")

    def describe(self) -> str:
        return self._prefix(
            f"Changed {self.type_name} `{self.name}` {self.prop} from {self.from_value} to {self.to_value}"
        )


@dataclass(frozen=True, order=True)
class AddedClassBase(ApiChange):
    """Added base class to a class."""

    value: str
    position: int

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="+")

    def describe(self) -> str:
        return self._prefix(
            f"Added base class `{self.value}` to `{self.name}` at position {self.position}"
        )


@dataclass(frozen=True, order=True)
class RemovedClassBase(ApiChange):
    """Removed base class from a class."""

    value: str
    position: int

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="-")

    def describe(self) -> str:
        return self._prefix(
            f"Removed base class `{self.value}` from `{self.name}` at position {self.position}"
        )


@dataclass(frozen=True, order=True)
class ModifiedClassBase(ApiChange):
    """Modified base class of a class."""

    position: int
    from_value: str
    to_value: str

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="!")

    def describe(self) -> str:
        return self._prefix(
            f"Modified base class of `{self.name}` at position {self.position} from `{self.from_value}` to `{self.to_value}`"
        )


@dataclass(frozen=True, order=True)
class AddedDecorator(ApiChange):
    """Added decorator to a function or class."""

    type_name: str
    value: str
    position: int

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="+")

    def describe(self) -> str:
        return self._prefix(
            f"Added decorator `{self.value}` to {self.type_name} `{self.name}` at position {self.position}"
        )


@dataclass(frozen=True, order=True)
class RemovedDecorator(ApiChange):
    """Removed decorator from a function or class."""

    type_name: str
    value: str
    position: int

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="-")

    def describe(self) -> str:
        return self._prefix(
            f"Removed decorator `{self.value}` from {self.type_name} `{self.name}` at position {self.position}"
        )


@dataclass(frozen=True, order=True)
class ModifiedDecorator(ApiChange):
    """Modified decorator of a function or class."""

    type_name: str
    position: int
    from_value: str
    to_value: str

    _diff_symbol: Literal["+", "-", "#", "!"] = field(init=False, default="!")

    def describe(self) -> str:
        return self._prefix(
            f"Modified decorator of `{self.name}` at position {self.position} from `{self.from_value}` to `{self.to_value}`"
        )


def _get_member_from_path(module: ModuleMember, path: list[str]) -> ApiMember:
    """Get the last member from a path (linked-list traversal)."""
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
    """List the API changes between two modules."""

    def _parse(input_module):
        if isinstance(input_module, str):
            return ModuleMember(node=ast.parse(input_module))
        elif isinstance(input_module, ast.Module):
            return ModuleMember(node=input_module)
        return input_module

    old_module = _parse(old_module)
    new_module = _parse(new_module)

    output: list[ApiChange] = []

    for row in Delta(
        DeepDiff(old_module, new_module, exclude_regex_paths=r".*\.(?:node|path)"),
        bidirectional=True,
    ).to_flat_rows():

        path = row.path
        action = row.action
        value = row.value
        old_value = getattr(row, "old_value", None)

        def make_path(obj):
            return ".".join(obj.path[:-1])

        def make_name(obj):
            return obj.path[-1]

        if action == "dictionary_item_added" and isinstance(value, ApiMember):
            output.append(Added(make_path(value), make_name(value), value.type_name))

        elif action == "dictionary_item_removed" and isinstance(value, ApiMember):
            output.append(Removed(make_path(value), make_name(value), value.type_name))

        elif action == "type_changes" and isinstance(value, ApiMember):
            output.append(
                TypeChanged(make_path(value), make_name(value), old_value.type_name, value.type_name)  # type: ignore
            )

        elif (
            action == "values_changed"
            and path[-1] == "members"
            and isinstance(value, dict)
        ):
            for member in old_value.values():  # type: ignore
                output.append(
                    Removed(make_path(member), make_name(member), member.type_name)
                )
            for member in value.values():
                output.append(
                    Added(make_path(member), make_name(member), member.type_name)
                )

        elif action == "values_changed" and len(path) > 1:
            obj = _get_member_from_path(old_module, path[:-1])
            if path[-2] == "bases":
                output.append(
                    ModifiedClassBase(make_path(obj), make_name(obj), path[-1], old_value, value)  # type: ignore
                )
            elif path[-2] == "decorators":
                output.append(
                    ModifiedDecorator(make_path(obj), make_name(obj), obj.type_name, path[-1], old_value, value)  # type: ignore
                )
            else:
                output.append(
                    Modified(
                        make_path(obj),
                        make_name(obj),
                        obj.type_name,
                        path[-1],
                        old_value,
                        value,
                    )
                )

        elif action == "iterable_item_added" and path[-2] == "decorators":
            obj = _get_member_from_path(old_module, path[:-1])
            output.append(
                AddedDecorator(make_path(obj), make_name(obj), obj.type_name, value, path[-1])  # type: ignore
            )

        elif action == "iterable_item_removed" and path[-2] == "decorators":
            obj = _get_member_from_path(old_module, path[:-1])
            output.append(
                RemovedDecorator(make_path(obj), make_name(obj), obj.type_name, value, path[-1])  # type: ignore
            )

        elif action == "iterable_item_added" and path[-2] == "bases":
            obj = _get_member_from_path(old_module, path[:-1])
            output.append(
                AddedClassBase(make_path(obj), make_name(obj), value, path[-1])  # type: ignore
            )

        elif action == "iterable_item_removed" and path[-2] == "bases":
            obj = _get_member_from_path(old_module, path[:-1])
            output.append(
                RemovedClassBase(make_path(obj), make_name(obj), value, path[-1])  # type: ignore
            )

        else:
            logging.error(f"Unknown change: {row}")

    return output
