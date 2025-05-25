from unittest import TestCase
import pathlib
import sys
from textwrap import dedent

sys.path.append(str(pathlib.Path(__file__).parent.parent.resolve()))

from difflog import (
    diff,
    Removed,
    Added,
    Modified,
    TypeChanged,
    RemovedClassBase,
    AddedClassBase,
    RemovedDecorator,
    AddedDecorator,
    ModifiedDecorator,
)


class TestApiDiffing(TestCase):
    def test_identical(self):
        self.assertEqual(set(diff("x: int = 1", "x: int = 1")), set())

    def test_removed(self):
        self.assertEqual(
            set(diff("x: int = 1", "")),
            {Removed(path="", name="x", type_name="attribute")},
        )

    def test_added(self):
        self.assertEqual(
            set(diff("", "x: int = 1")),
            {Added(path="", name="x", type_name="attribute")},
        )

    def test_modified(self):
        self.assertEqual(
            set(diff("x: int = 1", "x: int = 2")),
            {
                Modified(
                    path="",
                    name="x",
                    type_name="attribute",
                    prop="value",
                    from_value="1",
                    to_value="2",
                )
            },
        )

    def test_renamed(self):
        self.assertEqual(
            set(diff("x: int = 1", "y: int = 1")),
            {
                Removed(path="", name="x", type_name="attribute"),
                Added(path="", name="y", type_name="attribute"),
            },
        )

    def test_type_changed(self):
        self.assertEqual(
            set(diff("x: int = 1", "def x() -> str: pass")),
            {TypeChanged(path="", name="x", from_type="attribute", to_type="function")},
        )

    def test_function_arg_changes(self):
        script1 = dedent(
            """
            def bar(a: int, b: int = 1, *args: int, **kwargs: int) -> str: pass
        """
        )

        script2 = dedent(
            """
            def bar(b: int = 2, a: int = 3, *args: int, **kwargs: int) -> str: pass
        """
        )

        self.assertEqual(
            set(diff(script1, script2)),
            {
                Modified(
                    path="bar",
                    name="a",
                    type_name="positional or keyword argument",
                    prop="position",
                    from_value=0,
                    to_value=1,
                ),
                Modified(
                    path="bar",
                    name="b",
                    type_name="positional or keyword argument",
                    prop="position",
                    from_value=1,
                    to_value=0,
                ),
                Modified(
                    path="bar",
                    name="b",
                    type_name="positional or keyword argument",
                    prop="default",
                    from_value="1",
                    to_value="2",
                ),
                Modified(
                    path="bar",
                    name="a",
                    type_name="positional or keyword argument",
                    prop="default",
                    from_value="",
                    to_value="3",
                ),
            },
        )

    def test_nested_functions(self):
        script1 = dedent(
            """
            class Foo:
                def bar() -> str: pass
        """
        )

        script2 = dedent(
            """
            class Foo:
                def baz() -> str: pass
        """
        )

        output = set(diff(script1, script2))

        self.assertEqual(
            output,
            {
                Removed(path="Foo", name="bar", type_name="function"),
                Added(path="Foo", name="baz", type_name="function"),
            },
        )

        script1 = dedent(
            """
            class Foo:
                def bar() -> str: pass
        """
        )

        script2 = dedent(
            """
            class Foo:
                def bar() -> int: pass
        """
        )

        output = set(diff(script1, script2))

        self.assertEqual(
            output,
            {
                Modified(
                    path="Foo",
                    name="bar",
                    type_name="function",
                    prop="returns",
                    from_value="str",
                    to_value="int",
                )
            },
        )

    def test_class_bases_changed(self):
        script1 = dedent(
            """
            class Foo:
                pass
        """
        )

        script2 = dedent(
            """
            class Foo(int):
                pass
        """
        )

        output = set(diff(script1, script2))

        self.assertEqual(
            output,
            {
                AddedClassBase(path="", name="Foo", value="int", position=0),
            },
        )

        script1 = dedent(
            """
            class Foo(int):
                pass
        """
        )

        script2 = dedent(
            """
            class Foo:
                pass
        """
        )

        output = set(diff(script1, script2))

        self.assertEqual(
            output,
            {
                RemovedClassBase(path="", name="Foo", value="int", position=0),
            },
        )

    def test_decorators(self):
        script1 = dedent(
            """
            @decorator
            def foo() -> str: pass
        """
        )

        script2 = dedent(
            """
            @decorator2
            def foo() -> str: pass
        """
        )

        output = set(diff(script1, script2))

        self.assertEqual(
            output,
            {
                ModifiedDecorator(
                    path="",
                    name="foo",
                    type_name="function",
                    position=0,
                    from_value="decorator",
                    to_value="decorator2",
                )
            },
        )

        script1 = dedent(
            """
            @decorator
            def foo() -> str: pass
        """
        )

        script2 = dedent(
            """
            def foo() -> str: pass
        """
        )

        output = set(diff(script1, script2))

        self.assertEqual(
            output,
            {
                RemovedDecorator(
                    path="",
                    name="foo",
                    type_name="function",
                    position=0,
                    value="decorator",
                )
            },
        )

        script1 = dedent(
            """
            def foo() -> str: pass
        """
        )

        script2 = dedent(
            """
            @decorator
            def foo() -> str: pass
        """
        )

        output = set(diff(script1, script2))

        self.assertEqual(
            output,
            {
                AddedDecorator(
                    path="",
                    name="foo",
                    type_name="function",
                    position=0,
                    value="decorator",
                )
            },
        )
