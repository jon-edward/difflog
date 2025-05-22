"""
This module contains classes for parsing Python API members from an AST.

API members are any attribute, function or class that can be accessed 
from an import. This does not include attributes, functions or classes
defined inside functions, but does include attributes, 
functions or classes defined inside classes.
"""

from abc import abstractmethod, ABC
import ast
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Member(ABC):
    """
    Base class for all members.
    """
    path: tuple[str] = field(default_factory=tuple)
    lineno: int = None
    end_lineno: int = None

    @classmethod
    @abstractmethod
    def from_ast(cls, node: ast.AST) -> "Member":
        raise NotImplementedError
    
    def __getitem__(self, key):
        return getattr(self, key)


@dataclass
class AttributeMember(Member):
    """
    Attribute member, parsed from a statement of the form:

    ```python
    a = 1
    a: int
    a: int = 1
    ```
    """

    annotation: str = None
    value: str = None

    @classmethod
    def from_ast(cls, node: ast.AnnAssign | ast.Assign) -> "AttributeMember":
        if isinstance(node, ast.AnnAssign):
            annotation = node.annotation
        else:
            annotation = None

        return cls(
            lineno=node.lineno,
            end_lineno=node.end_lineno,
            annotation=ast.unparse(annotation) if annotation else None,
            value=ast.unparse(node.value) if node.value else None,
        )


@dataclass
class Argument:
    """
    Base class for function arguments.
    """
    path: tuple[str] = field(default_factory=tuple)
    annotation: str = None

    def __getitem__(self, key):
        return getattr(self, key)


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
    default: str = None


@dataclass
class ArgumentVarPositional(Argument):
    """
    Var positional argument. Parsed from a statement of the form:

    ```python
    def foo(*a: int): pass
    ```

    Where `a` is a var positional argument.
    """


@dataclass
class ArgumentVarKeyword(Argument):
    """
    Var keyword argument. Parsed from a statement of the form:

    ```python
    def foo(**a: int): pass
    ```

    Where `a` is a var keyword argument.
    """


@dataclass
class ArgumentKeywordOnly(Argument):
    """
    Keyword-only argument. Parsed from a statement of the form:

    ```python
    def foo(*, a: int): pass
    ```

    Where `a` is a keyword-only argument.
    """

    default: str = None


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
    default: str = None


@dataclass
class FunctionMember(Member):
    """
    Function or async function member.
    """

    arguments: dict[str, Argument] = field(default_factory=dict)
    returns: str = None
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)

    @classmethod
    def from_ast(cls, node: ast.FunctionDef | ast.AsyncFunctionDef, path: tuple[str] = None) -> "FunctionMember":
        instance = cls(
            lineno=node.lineno,
            end_lineno=node.end_lineno,
            returns=ast.unparse(node.returns) if node.returns else None,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=[ast.unparse(expr) for expr in node.decorator_list],
        )

        instance.path = path

        padded_defaults = [None] * (
            len(node.args.posonlyargs) + len(node.args.args) - len(node.args.defaults)
        ) + node.args.defaults

        for position, (arg, default) in enumerate(
            zip(node.args.posonlyargs, padded_defaults[: len(node.args.posonlyargs)])
        ):
            instance.arguments[arg.arg] = ArgumentPositionalOnly(
                position=position,
                annotation=ast.unparse(arg.annotation) if arg.annotation else None,
                default=ast.unparse(default) if default else None,
            )
            instance.arguments[arg.arg].path = path + (arg.arg,)

        for position, (arg, default) in enumerate(
            zip(node.args.args, padded_defaults[len(node.args.posonlyargs) :]),
            len(node.args.posonlyargs),
        ):
            instance.arguments[arg.arg] = ArgumentPositionalOrKeyword(
                position=position,
                annotation=ast.unparse(arg.annotation) if arg.annotation else None,
                default=ast.unparse(default) if default else None,
            )
            instance.arguments[arg.arg].path = path + (arg.arg,)

        if node.args.vararg:
            instance.arguments[node.args.vararg.arg] = ArgumentVarPositional(
                annotation=(
                    ast.unparse(node.args.vararg.annotation)
                    if node.args.vararg.annotation
                    else None
                ),
            )
            instance.arguments[node.args.vararg.arg].path = path + (node.args.vararg.arg,)

        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            instance.arguments[arg.arg] = ArgumentKeywordOnly(
                annotation=ast.unparse(arg.annotation) if arg.annotation else None,
                default=ast.unparse(default) if default else None,
            )
            instance.arguments[arg.arg].path = path + (arg.arg,)

        if node.args.kwarg:
            instance.arguments[node.args.kwarg.arg] = ArgumentVarKeyword(
                annotation=(
                    ast.unparse(node.args.kwarg.annotation)
                    if node.args.kwarg.annotation
                    else None
                ),
            )
            instance.arguments[node.args.kwarg.arg].path = path + (node.args.kwarg.arg,)

        return instance

def _default_check_name_fn(_path: list[str], name: str) -> bool:
    if name.startswith("_") and (name == "_" or not name.endswith("_")):
        # Private attribute (i.e. `_private_var`, `__private_var`, but not `__dunder__`)
        return False
    return True

@dataclass
class Namespace(Member):
    """
    This type is for modules and classes.
    """
    classes: dict[str, "Namespace"] = field(default_factory=dict)
    attributes: dict[str, AttributeMember] = field(default_factory=dict)
    functions: dict[str, FunctionMember] = field(default_factory=dict)
    decorators: list[str] = field(default_factory=list)

    check_name_fn: Callable[[list[str], str], bool] = field(default=_default_check_name_fn)
    """
    Check if a name should be included in the namespace.

    The first argument is the path to the current namespace. When inspecting a shallow module, the path is an empty list. 
    When inspecting the top-level class `Foo` of a module, the path is `["Foo"]`. When inspecting the second-level 
    class `Bar` of the same module, the path is `["Foo", "Bar"]`.
    
    The second argument is the name of the current member.
    """

    @classmethod
    def from_ast(cls, node: ast.Module | ast.ClassDef, check_name_fn: Callable[[str], bool] = None, path: tuple[str] = None) -> "Namespace":
        if path is None:
            path = ()
        
        if isinstance(node, ast.Module):
            lineno = None
            end_lineno = None
        else:
            lineno = node.lineno
            end_lineno = node.end_lineno

        instance = cls(lineno=lineno, end_lineno=end_lineno)
        instance.path = path

        if check_name_fn:
            instance.check_name_fn = check_name_fn

        if isinstance(node, ast.ClassDef):
            instance.decorators = [ast.unparse(expr) for expr in node.decorator_list]

        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                name = child.name
                
                if not instance.check_name_fn(path, name):
                    continue
                
                instance.classes[name] = cls.from_ast(child, check_name_fn=instance.check_name_fn, path=path + (name,))
                instance.classes[name].path = path + (name,)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
                
                if not instance.check_name_fn(path, name):
                    continue
                
                instance.functions[name] = FunctionMember.from_ast(child, path + (name,))
            elif isinstance(child, ast.AnnAssign):
                name = (
                    child.target.id
                    if isinstance(child.target, ast.Name)
                    else ast.unparse(child.target)
                )

                if not instance.check_name_fn(path, name):
                    continue
                
                instance.attributes[name] = AttributeMember.from_ast(child)
                instance.attributes[name].path = path + (name,)
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    # Potentially multiple targets, as in `a = b = 2`
                    # each one should be a separate attribute, and visiting 
                    # the same attribute twice will overwrite the value
                    name = (
                        target.id
                        if isinstance(target, ast.Name)
                        else ast.unparse(target)
                    )

                    if not instance.check_name_fn(path, name):
                        continue
                    
                    instance.attributes[name] = AttributeMember.from_ast(child)
                    instance.attributes[name].path = path + (name,)

        return instance


if __name__ == "__main__":
    script = """

a = 1
c: int = 2
d: str
a -= 1
_ = 1

x1, x2, x3 = 1, 2, 3

y1 = y2 = y3 = 1

@function_decorator
def foo(start, a: int, /, b: int = 1, *args: int, **kwargs: int) -> str:
    do_not_include = 1_000
    return ""

@decorator
class Foo:
    b: int
    a: int = 1

    @another_decorator
    class Bar:
        x: int

    def __init__(self):
        self.a = 1

"""
    import pprint

    print(f"=== Parsing script: === \n{script}\n===")
    pprint.pprint(Namespace.from_ast(ast.parse(script)))
