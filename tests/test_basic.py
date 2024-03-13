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
from textwrap import dedent

import pytest

from blockyaml import (
    Converter,
    DataclassConverter,
    Parser,
    YAMLConstructorError,
    YAMLDataclassExtraFieldsError,
    YAMLDataclassMissingFieldsError,
    YAMLParserError,
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
        assert (
            parser.parse_str(
                """
            k0: 4
            k1: hi
        """
            )
            == {"k0": 4, "k1": "hi"}
        )
        assert (
            parser.parse_str(
                """
            - 4
            - hi
        """
            )
            == [4, "hi"]
        )
        assert (
            parser.parse_str(
                """
            - 4
            - x: 0
              y: [1]
        """
            )
            == [4, {"x": 0, "y": [1]}]
        )

    def test_primitive_checking(self):
        parser = Parser()

        with pytest.raises(YAMLConstructorError):
            parser.parse_str(
                """
                k0: 4
                k1: hi,
                k0: 5
            """
            )

        with pytest.raises(YAMLConstructorError):
            parser.parse_str("no")

        with pytest.raises(YAMLConstructorError):
            parser.parse_str("22:22")

        with pytest.raises(YAMLConstructorError):
            parser.parse_str("!.html")

    def test_tags(self):
        parser = Parser()

        # Test a simple string converter
        @parser.register(str, tag="!Upper")
        class Capitalise(Converter):
            def construct_scalar(self, loader, node):
                return node.value.upper()

        assert parser.parse_str("!Upper mYGarBaGeCASe") == "MYGARBAGECASE"

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
        with pytest.raises(YAMLDataclassMissingFieldsError):
            date = parser.parse_str(
                """
            !Date
            month: June
            """
            )

        # Test extra field
        with pytest.raises(YAMLDataclassExtraFieldsError):
            date = parser.parse_str(
                """
            !Date
            month: June
            week: 1
            hour: 4
            """
            )

        # Test object specific parsing works
        with pytest.raises(YAMLParserError):
            parser(Date).parse_str("hello")

        assert isinstance(parser(Date).parse_str(dateyaml), Date)

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
