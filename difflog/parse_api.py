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
    """
    Base class for all API members.
    """

    path: list[str]

    @property
    @abstractmethod
    def type_name(self) -> str:
        raise NotImplementedError

    def __getitem__(self, key: str):
        return getattr(self, key)


@dataclass
class _AstApiMember(ApiMember, ABC):
    """
    Base class for API members parsed from an AST node.
    """

    node: ast.AST = field(kw_only=True)


@dataclass
class AttributeMember(_AstApiMember):
    """
    Attribute member, parsed from a statement of the form:

    ```python
    a = 1
    a: int
    a: int = 1
    ```
    """

    node: ast.AnnAssign | ast.Assign = field(kw_only=True)  # type: ignore

    annotation: str = field(init=False)
    value: str = field(init=False)

    @property
    def type_name(self):
        return "attribute"

    def __post_init__(self):
        if isinstance(self.node, ast.AnnAssign):
            self.annotation = ast.unparse(self.node.annotation)
        else:
            self.annotation = ""

        self.value = ast.unparse(self.node.value) if self.node.value else ""


@dataclass
class Argument(ApiMember, ABC):
    annotation: str = ""


@dataclass
class ArgumentPositionalOrKeyword(Argument):
    """
    Positional or keyword argument. Parsed from a statement of the form:

    ```python
    def foo(a: int, b: int = 1): pass
    ```

    Where `a` and `b` are both positional or keyword arguments, and `b` has a default.
    """

    position: int = field(kw_only=True)
    default: str = ""

    @property
    def type_name(self):
        return "positional or keyword argument"


@dataclass
class ArgumentVarPositional(Argument):
    """
    Var positional argument. Parsed from a statement of the form:

    ```python
    def foo(*a: int): pass
    ```

    Where `a` is a var positional argument.
    """

    @property
    def type_name(self):
        return "var positional argument"


@dataclass
class ArgumentVarKeyword(Argument):
    """
    Var keyword argument. Parsed from a statement of the form:

    ```python
    def foo(**a: int): pass
    ```

    Where `a` is a var keyword argument.
    """

    @property
    def type_name(self):
        return "var keyword argument"


@dataclass
class ArgumentKeywordOnly(Argument):
    """
    Keyword-only argument. Parsed from a statement of the form:

    ```python
    def foo(*, a: int): pass
    ```

    Where `a` is a keyword-only argument.
    """

    default: str = ""

    @property
    def type_name(self):
        return "keyword-only argument"


@dataclass
class ArgumentPositionalOnly(Argument):
    """
    Positional-only argument. Parsed from a statement of the form:

    ```python
    def foo(a: int, /, b: int): pass
    ```

    Where `a` is a positional-only argument.
    """

    position: int = field(kw_only=True)
    default: str = ""

    @property
    def type_name(self):
        return "positional-only argument"


@dataclass
class FunctionMember(_AstApiMember):
    """
    Function member, parsed from a function definition.
    """

    node: ast.FunctionDef | ast.AsyncFunctionDef = field(kw_only=True)  # type: ignore

    # Derived attributes
    arguments: dict[str, Argument] = field(init=False, default_factory=dict)  # type: ignore
    returns: str = field(init=False)
    is_async: bool = field(init=False)
    decorators: list[str] = field(init=False, default_factory=list)  # type: ignore

    @property
    def type_name(self):
        return "function"

    def __post_init__(self):
        self.returns = ast.unparse(self.node.returns) if self.node.returns else ""
        self.is_async = isinstance(self.node, ast.AsyncFunctionDef)
        self.decorators = [ast.unparse(expr) for expr in self.node.decorator_list]

        self._parse_arguments()

    def _parse_arguments(self):
        padded_defaults = [None] * (
            len(self.node.args.posonlyargs)
            + len(self.node.args.args)
            - len(self.node.args.defaults)
        ) + self.node.args.defaults

        for position, (arg, default) in enumerate(
            zip(
                self.node.args.posonlyargs,
                padded_defaults[: len(self.node.args.posonlyargs)],
            )
        ):
            self.arguments[arg.arg] = ArgumentPositionalOnly(
                path=self.path
                + [
                    arg.arg,
                ],
                position=position,
                annotation=ast.unparse(arg.annotation) if arg.annotation else "",
                default=ast.unparse(default) if default else "",
            )

        for position, (arg, default) in enumerate(
            zip(
                self.node.args.args, padded_defaults[len(self.node.args.posonlyargs) :]
            ),
            len(self.node.args.posonlyargs),
        ):
            self.arguments[arg.arg] = ArgumentPositionalOrKeyword(
                path=self.path
                + [
                    arg.arg,
                ],
                position=position,
                annotation=ast.unparse(arg.annotation) if arg.annotation else "",
                default=ast.unparse(default) if default else "",
            )

        if self.node.args.vararg:
            self.arguments[self.node.args.vararg.arg] = ArgumentVarPositional(
                path=self.path
                + [
                    self.node.args.vararg.arg,
                ],
                annotation=(
                    ast.unparse(self.node.args.vararg.annotation)
                    if self.node.args.vararg.annotation
                    else ""
                ),
            )

        for arg, default in zip(self.node.args.kwonlyargs, self.node.args.kw_defaults):
            self.arguments[arg.arg] = ArgumentKeywordOnly(
                path=self.path + [arg.arg],
                annotation=ast.unparse(arg.annotation) if arg.annotation else "",
                default=ast.unparse(default) if default else "",
            )

        if self.node.args.kwarg:
            self.arguments[self.node.args.kwarg.arg] = ArgumentVarKeyword(
                path=self.path + [self.node.args.kwarg.arg],
                annotation=(
                    ast.unparse(self.node.args.kwarg.annotation)
                    if self.node.args.kwarg.annotation
                    else ""
                ),
            )


@dataclass
class NamespaceMember(_AstApiMember, ABC):
    """
    Namespace member, either a class or a module.
    """

    check_name_fn: Callable[[str], bool] = field(default=lambda _: True)

    members: dict[str, ApiMember] = field(init=False, default_factory=dict)  # type: ignore

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
                if not self.check_name_fn(name):
                    continue
                self.members[name] = AttributeMember(
                    path=self.path + [name], node=child
                )
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    name = ast.unparse(target)
                    if not self.check_name_fn(name):
                        continue
                    self.members[name] = AttributeMember(
                        path=self.path + [name], node=child
                    )


@dataclass
class ClassMember(NamespaceMember):

    node: ast.ClassDef = field(kw_only=True)  # type: ignore

    # Derived attributes
    bases: list[str] = field(init=False)
    decorators: list[str] = field(init=False)

    @property
    def type_name(self):
        return "class"

    def __post_init__(self):
        super().__post_init__()

        self.bases = [ast.unparse(expr) for expr in self.node.bases]
        self.decorators = [ast.unparse(expr) for expr in self.node.decorator_list]


@dataclass
class ModuleMember(NamespaceMember):
    """
    Module member, parsed from a module definition.
    """

    node: ast.Module = field(kw_only=True)  # type: ignore

    path: list[str] = field(init=False, default_factory=list)  # type: ignore
    """
    Module members have an empty path.
    """

    @property
    def type_name(self):
        return "module"
