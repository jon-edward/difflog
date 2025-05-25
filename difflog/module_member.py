from abc import ABC, abstractmethod
import ast
from dataclasses import dataclass, field
from typing import Callable

__all__ = (
    "ApiMember",
    "AttributeMember",
    "FunctionMember",
    "ClassMember",
    "ModuleMember",
    "NamespaceMember",
    "Argument",
    "ArgumentVarKeyword",
    "ArgumentVarPositional",
    "ArgumentPositionalOnly",
    "ArgumentPositionalOrKeyword",
    "ArgumentKeywordOnly",
)


@dataclass
class ApiMember:
    """Base class for all API members."""

    path: list[str]

    @property
    @abstractmethod
    def type_name(self) -> str:
        raise NotImplementedError

    def __getitem__(self, key: str):
        return getattr(self, key)


@dataclass
class _AstApiMember(ApiMember, ABC):
    """Base class for API members parsed from an AST node."""

    node: ast.AST = field(kw_only=True)


@dataclass
class AttributeMember(_AstApiMember):
    """Represents an attribute, parsed from `Assign` or `AnnAssign`."""

    node: ast.Assign | ast.AnnAssign = field(kw_only=True)

    annotation: str = field(init=False)
    value: str = field(init=False)

    @property
    def type_name(self) -> str:
        return "attribute"

    def __post_init__(self):
        if isinstance(self.node, ast.AnnAssign):
            self.annotation = ast.unparse(self.node.annotation)
        else:
            self.annotation = ""

        self.value = ast.unparse(self.node.value) if self.node.value else ""


@dataclass
class Argument(ApiMember, ABC):
    """Base class for function arguments."""

    annotation: str = ""


@dataclass
class ArgumentPositionalOrKeyword(Argument):
    """Represents a positional-or-keyword argument."""

    position: int = field(kw_only=True)
    default: str = ""

    @property
    def type_name(self) -> str:
        return "positional or keyword argument"


@dataclass
class ArgumentPositionalOnly(Argument):
    """Represents a positional-only argument."""

    position: int = field(kw_only=True)
    default: str = ""

    @property
    def type_name(self) -> str:
        return "positional-only argument"


@dataclass
class ArgumentKeywordOnly(Argument):
    """Represents a keyword-only argument."""

    default: str = ""

    @property
    def type_name(self) -> str:
        return "keyword-only argument"


@dataclass
class ArgumentVarPositional(Argument):
    """Represents a variable positional argument (e.g., *args)."""

    @property
    def type_name(self) -> str:
        return "var positional argument"


@dataclass
class ArgumentVarKeyword(Argument):
    """Represents a variable keyword argument (e.g., **kwargs)."""

    @property
    def type_name(self) -> str:
        return "var keyword argument"


@dataclass
class FunctionMember(_AstApiMember):
    """Represents a function, parsed from a function definition."""

    node: ast.FunctionDef | ast.AsyncFunctionDef = field(kw_only=True)

    arguments: dict[str, Argument] = field(init=False, default_factory=dict)
    returns: str = field(init=False)
    is_async: bool = field(init=False)
    decorators: list[str] = field(init=False, default_factory=list)

    @property
    def type_name(self) -> str:
        return "function"

    def __post_init__(self):
        self.returns = ast.unparse(self.node.returns) if self.node.returns else ""
        self.is_async = isinstance(self.node, ast.AsyncFunctionDef)
        self.decorators = [ast.unparse(expr) for expr in self.node.decorator_list]
        self._parse_arguments()

    def _parse_arguments(self):
        posonly = self.node.args.posonlyargs
        args = self.node.args.args
        defaults = self.node.args.defaults

        padded_defaults = [None] * (len(posonly) + len(args) - len(defaults)) + defaults

        # Positional-only args
        for i, (arg, default) in enumerate(
            zip(posonly, padded_defaults[: len(posonly)])
        ):
            self.arguments[arg.arg] = ArgumentPositionalOnly(
                path=self.path + [arg.arg],
                position=i,
                annotation=ast.unparse(arg.annotation) if arg.annotation else "",
                default=ast.unparse(default) if default else "",
            )

        # Positional or keyword args
        for i, (arg, default) in enumerate(
            zip(args, padded_defaults[len(posonly) :]), len(posonly)
        ):
            self.arguments[arg.arg] = ArgumentPositionalOrKeyword(
                path=self.path + [arg.arg],
                position=i,
                annotation=ast.unparse(arg.annotation) if arg.annotation else "",
                default=ast.unparse(default) if default else "",
            )

        # *args
        if self.node.args.vararg:
            arg = self.node.args.vararg
            self.arguments[arg.arg] = ArgumentVarPositional(
                path=self.path + [arg.arg],
                annotation=ast.unparse(arg.annotation) if arg.annotation else "",
            )

        # Keyword-only args
        for arg, default in zip(self.node.args.kwonlyargs, self.node.args.kw_defaults):
            self.arguments[arg.arg] = ArgumentKeywordOnly(
                path=self.path + [arg.arg],
                annotation=ast.unparse(arg.annotation) if arg.annotation else "",
                default=ast.unparse(default) if default else "",
            )

        # **kwargs
        if self.node.args.kwarg:
            arg = self.node.args.kwarg
            self.arguments[arg.arg] = ArgumentVarKeyword(
                path=self.path + [arg.arg],
                annotation=ast.unparse(arg.annotation) if arg.annotation else "",
            )


@dataclass
class NamespaceMember(_AstApiMember, ABC):
    """Represents a namespace (class or module) with nested members."""

    check_name_fn: Callable[[str], bool] = field(default=lambda _: True)
    members: dict[str, ApiMember] = field(init=False, default_factory=dict)

    def __post_init__(self):
        for child in ast.iter_child_nodes(self.node):
            if isinstance(child, ast.ClassDef):
                name = child.name
                if not self.check_name_fn(name):
                    continue
                self.members[name] = ClassMember(
                    path=self.path + [name],
                    node=child,
                    check_name_fn=self.check_name_fn,
                )
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
                if not self.check_name_fn(name):
                    continue
                self.members[name] = FunctionMember(path=self.path + [name], node=child)
            elif isinstance(child, ast.AnnAssign):
                name = ast.unparse(child.target)
                if self.check_name_fn(name):
                    self.members[name] = AttributeMember(
                        path=self.path + [name], node=child
                    )
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    name = ast.unparse(target)
                    if self.check_name_fn(name):
                        self.members[name] = AttributeMember(
                            path=self.path + [name], node=child
                        )


@dataclass
class ClassMember(NamespaceMember):
    """Represents a class definition."""

    node: ast.ClassDef = field(kw_only=True)

    bases: list[str] = field(init=False)
    decorators: list[str] = field(init=False)

    @property
    def type_name(self) -> str:
        return "class"

    def __post_init__(self):
        super().__post_init__()
        self.bases = [ast.unparse(expr) for expr in self.node.bases]
        self.decorators = [ast.unparse(expr) for expr in self.node.decorator_list]


@dataclass
class ModuleMember(NamespaceMember):
    """Represents a module, the root of the AST tree."""

    node: ast.Module = field(kw_only=True)
    path: list[str] = field(init=False, default_factory=list)

    @property
    def type_name(self) -> str:
        return "module"
