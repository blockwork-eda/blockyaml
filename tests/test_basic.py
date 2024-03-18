# Copyright 2024, Blockwork, https://github.com/blockwork-eda/blockwork
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest

from blockyaml import (
    Converter,
    DataclassConverter,
    Parser,
)
from blockyaml.exceptions import (
    YAMLConstructorInvalidTypeError,
    YAMLConstructorMissingError,
    YAMLConstructorMultipleImplicitError,
    YAMLConstructorNotImplementedError,
    YAMLRegistrationTypeError,
    YAMLRepresenterMissingError,
    YAMLRepresenterNotImplementedError,
    YAMLStrictBoolError,
    YAMLStrictKeyError,
    YAMLStrictNumberError,
)
from blockyaml.loader import (
    decompose_dict_type,
    decompose_list_type,
    decompose_scalar_type,
    flatten_type,
)


def fixup(yml):
    return dedent(yml).lstrip()


class TestBasic:
    def test_native_types(self):
        parser = Parser()

        assert parser.parse_str("hello") == "hello"
        assert parser.parse_str("4") == 4
        assert parser.parse_str("4.2") == 4.2
        assert parser.parse_str("4.2.1") == "4.2.1"
        assert parser.parse_str("True") is True
        assert parser.parse_str(
            """
            k0: 4
            k1: hi
        """
        ) == {"k0": 4, "k1": "hi"}
        assert parser.parse_str(
            """
            - 4
            - hi
        """
        ) == [4, "hi"]
        assert parser.parse_str(
            """
            - 4
            - x: 0
              y: [1]
        """
        ) == [4, {"x": 0, "y": [1]}]

    def test_tags(self):
        parser = Parser()

        # Test a simple string converter
        @parser.register(str, tag="!Upper")
        class Capitalise(Converter):
            def construct_scalar(self, loader, node):
                return node.value.upper()

        assert parser.parse_str("!Upper mYGarBaGeCASe") == "MYGARBAGECASE"

        # Test converter registry
        class Rect:
            def __init__(self, x: int, y: int):
                self.x = x
                self.y = y

        @parser.register(Rect)
        class RectConverter(Converter):
            def construct_mapping(self, loader, node):
                mapping = loader.construct_mapping(node, deep=True)
                return Rect(x=mapping["x"], y=mapping["y"])

            def represent_node(self, dumper, value):
                return dumper.represent_mapping(self.tag, {"x": value.x, "y": value.y})

        rectyaml = """
        !Rect
        x: 2
        y: 4
        """
        rect = parser(Rect).parse_str(rectyaml)
        assert rect.x == 2 and rect.y == 4
        assert parser.dump_str(rect) == fixup(rectyaml)

    def test_decomposition(self):
        # Check flattening unions works
        assert flatten_type(str) == (str,)
        assert flatten_type(str | int) == (
            str,
            int,
        )

        # Check decomposing scalar types works and...
        assert decompose_scalar_type(str) == (str,)
        assert decompose_scalar_type(str | int) == (
            str,
            int,
        )

        # Check decomposing list types works
        assert decompose_list_type(list) == ((list,), None)
        assert decompose_list_type(list[str]) == ((list,), str)
        assert decompose_list_type(list[str | int]) == ((list,), str | int)
        assert decompose_list_type(list[str] | list[int | float]) == ((list,), str | float | int)

        # Check decomposing dict types works
        assert decompose_dict_type(dict) == ((dict,), None, None)
        assert decompose_dict_type(dict[str, int]) == ((dict,), str, int)
        assert decompose_dict_type(dict[str | int, int]) == ((dict,), str | int, int)
        assert decompose_dict_type(dict[str | int, int | float]) == (
            (dict,),
            str | int,
            int | float,
        )
        assert decompose_dict_type(dict[str, int] | dict[float, str]) == (
            (dict,),
            float | str,
            str | int,
        )

    def test_inferance(self):
        "Test use of the infer option to parse using declared type"
        parser = Parser()

        @parser.register(Path, tag="!Path", infer=True)
        class PathConverter(Converter):
            def construct_scalar(self, loader, node):
                return Path(node.value)

        @parser.register(bytes, tag="!Bytes", infer=True)
        class BytesConverter(Converter):
            def construct_scalar(self, loader, node):
                return node.value.encode()

        # Check explicit None tag means converter can only be inferred
        class Dog:
            ...

        @parser.register(Dog, tag=None, infer=True)
        class DogConverter(Converter):
            def construct_scalar(self, loader, node):
                return Dog()

        with pytest.raises(YAMLConstructorMissingError):
            parser.parse_str("!Dog x")
        with pytest.raises(YAMLConstructorMissingError):
            parser(Dog).parse_str("!Dog x")
        assert isinstance(parser(Dog).parse_str("x"), Dog)

        # Check infer false means converter can't be inferred
        class Cat:
            ...

        @parser.register(Cat, infer=False)
        class CatConverter(Converter):
            def construct_scalar(self, loader, node):
                return Cat()

        with pytest.raises(YAMLConstructorInvalidTypeError):
            parser(Cat).parse_str("x")
        assert isinstance(parser.parse_str("!Cat x"), Cat)
        assert isinstance(parser(Cat).parse_str("!Cat x"), Cat)

        # Check that when typed parser is called, it correctly calls the
        # converter.
        assert isinstance(parser(Path).parse_str("/my/file/path"), Path)
        assert isinstance(parser(bytes).parse_str("/my/file/path"), bytes)

        # Check that when using a nested type, the converter is still used
        assert parser(dict[str, Path]).parse_str(
            """
        k1: /hello/
        k2: /world.lib
        """
        ) == {"k1": Path("/hello/"), "k2": Path("/world.lib")}

        # Check that we can descriminate unions based on structural types
        assert parser(Path | list[Path]).parse_str("/a/b") == Path("/a/b")
        assert parser(Path | list[Path]).parse_str("[/a/b,/c/d]") == [Path("/a/b"), Path("/c/d")]
        assert parser(dict[str, Path] | list[Path]).parse_str("{x/y: /a/b}") == {
            "x/y": Path("/a/b")
        }
        assert parser(dict[str, Path] | list[Path]).parse_str("[/a/b,/c/d]") == [
            Path("/a/b"),
            Path("/c/d"),
        ]

        # Check that we discriminate unions when a union type matches without
        # conversion
        assert parser(Path | None).parse_str("null") is None
        assert parser(Path | None).parse_str("/a/b") == Path("/a/b")
        assert parser(Path | str).parse_str("/my/not/path/") == "/my/not/path/"

        # Check that we can't discriminate unions when two types could be valid
        with pytest.raises(YAMLConstructorMultipleImplicitError):
            parser(Path | bytes).parse_str("/my/not/path/")

        # But check that we can if it's explicitely specified
        assert parser(Path | bytes).parse_str("!Path /my/path/") == Path("/my/path/")
        assert parser(Path | bytes).parse_str("!Bytes /my/bytes/") == b"/my/bytes/"

        # Check parameterised generics can't be used for conversion
        with pytest.raises(YAMLRegistrationTypeError):

            @parser.register(list[str], infer=True)
            class ListStrConverter(Converter):
                def construct_scalar(self, loader, node):
                    return [str(node.value)]

    def test_errors(self):
        parser = Parser()

        # Test explicit fall-throughs
        class Registered:
            ...

        @parser.register(Registered, tag="!Registered")
        class ConvertRegistered(Converter):
            ...

        with pytest.raises(YAMLConstructorNotImplementedError):
            parser.parse_str("!Registered")

        with pytest.raises(YAMLRepresenterNotImplementedError):
            parser.dump_str(Registered())

        # Test implicit fall throughs
        class Unregistered:
            ...

        with pytest.raises(YAMLConstructorMissingError):
            parser.parse_str("!Unregistered")

        with pytest.raises(YAMLRepresenterMissingError):
            parser.dump_str(Unregistered())

    def test_strict_implicit_converter(self):
        parser = Parser()

        with pytest.raises(YAMLStrictKeyError):
            parser.parse_str(
                """
                k0: 4
                k1: hi,
                k0: 5
            """
            )

        with pytest.raises(YAMLStrictBoolError):
            parser.parse_str("no")

        with pytest.raises(YAMLStrictNumberError):
            parser.parse_str("22:22")

        with pytest.raises(YAMLConstructorMissingError):
            parser.parse_str("!.html")

    def test_dataclass_converter(self):
        parser = Parser()

        # Test a dataclass converter
        @parser.register(DataclassConverter)
        @dataclass
        class Date:
            week: int
            month: str
            day: int = 3

        # Test correctly parsed and dumped
        dateyaml = """
        !Date
        day: 4
        month: June
        week: 1
        """
        date = parser.parse_str(dateyaml)
        assert isinstance(date, Date)
        assert date.day == 4 and date.week == 1 and date.month == "June"
        assert parser.dump_str(date) == fixup(dateyaml)

        # Test missing field with default
        date = parser.parse_str(
            """
        !Date
        month: June
        week: 1
        """
        )
        assert date.day == 3 and date.week == 1 and date.month == "June"

        # Test missing field without default
        with pytest.raises(Exception):  # noqa: B017 (temp)
            date = parser.parse_str(
                """
            !Date
            month: June
            """
            )

        # Test extra field
        with pytest.raises(Exception):  # noqa: B017 (temp)
            date = parser.parse_str(
                """
            !Date
            month: June
            week: 1
            hour: 4
            """
            )

        # Test object specific parsing works
        with pytest.raises(Exception):  # noqa: B017 (temp)
            parser(Date).parse_str("hello")

        assert isinstance(parser(Date).parse_str(dateyaml), Date)
