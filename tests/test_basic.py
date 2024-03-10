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
import pytest
from textwrap import dedent
from blockyaml import Parser, YamlConstructorError, Converter, DataclassConverter, YamlMissingFieldsError, YamlExtraFieldsError

def fixup(yml):
    return dedent(yml).lstrip()

class TestBasic:
    def test_native_types(self):
        parser =  Parser()

        assert parser.parse_str("hello") == "hello"
        assert parser.parse_str("4") == 4
        assert parser.parse_str("4.2") == 4.2
        assert parser.parse_str("4.2.1") == "4.2.1"
        assert parser.parse_str("True") == True
        assert parser.parse_str("""
            k0: 4
            k1: hi
        """) == { 'k0': 4, 'k1': 'hi' }
        assert parser.parse_str("""
            - 4
            - hi
        """) == [4, 'hi']
        assert parser.parse_str("""
            - 4
            - x: 0
              y: [1]
        """) == [4, {'x':0, 'y':[1]}]

    def test_primitive_checking(self):
        parser = Parser()

        with pytest.raises(YamlConstructorError):
            parser.parse_str("""
                k0: 4
                k1: hi,
                k0: 5
            """)

        with pytest.raises(YamlConstructorError):
            parser.parse_str("no")

        with pytest.raises(YamlConstructorError):
            parser.parse_str("22:22")

        with pytest.raises(YamlConstructorError):
            parser.parse_str("!.html")

    def test_tags(self):
        parser = Parser()

        # Test a simple string converter
        class Capitalise(Converter):
            def construct_scalar(self, loader, node):
                return node.value.upper()

        parser.register(Capitalise, tag="!Upper")(str)

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
        date = parser.parse_str("""
        !Date
        month: June
        week: 1
        """)
        assert date.day == 3 and date.week == 1 and date.month == "June"

        # Test missing field without default
        with pytest.raises(YamlMissingFieldsError):
            date = parser.parse_str("""
            !Date
            month: June
            """)

        # Test extra field
        with pytest.raises(YamlExtraFieldsError):
            date = parser.parse_str("""
            !Date
            month: June
            week: 1
            hour: 4
            """)
