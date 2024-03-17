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

from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, Self, TextIO, overload

from yaml import dump, load

from .converters import (
    Converter,
    ConverterRegistry,
    ImplicitConverter,
    StrictImplicitConverter,
    _Convertable,
)
from .types import Dumper, Loader, YAMLError


class YAMLParserError(YAMLError):
    "Error parsing yaml"

    def __init__(self, location: Path | str, msg: str):
        self.location = location
        self.msg = msg

    def __str__(self):
        return f"{self.location}: {self.msg}"


class ObjectParser(Generic[_Convertable]):
    """Yaml parser for a specific type, created by ParserFactory"""

    def __init__(self, typ: type[_Convertable], loader: type[Loader], dumper: type[Dumper]):
        self.typ = typ
        self.loader = loader
        self.dumper = dumper

    def parse(self, path: Path | TextIO) -> _Convertable:
        """
        Parse a YAML file from disk and return the object it contains.

        :param path: Where to read the yaml from
        :returns:    Parsed object
        """
        with self.loader.expected_type(self.typ):
            if isinstance(path, Path):
                with path.open("r", encoding="utf-8") as fh:
                    parsed: _Convertable = load(fh, Loader=self.loader)
            else:
                parsed: _Convertable = load(path, Loader=self.loader)

        return parsed

    def parse_str(self, data: str) -> _Convertable:
        """
        Parse a YAML string and return the object it contains.

        :param data: YAML string
        :returns:    Parsed object
        """
        with self.loader.expected_type(self.typ):
            parsed: _Convertable = load(data, Loader=self.loader)
        return parsed

    def dump(self, obj: Any, path: Path | TextIO) -> None:
        """
        Dump an object to YAML and write it to the path or file handle
        provided.

        :param obj:  The object to dump
        :param path: Where to write the YAML to
        """
        if isinstance(path, Path):
            with path.open("w", encoding="utf-8") as fh:
                dump(obj, fh, Dumper=self.dumper)
        else:
            dump(obj, path, Dumper=self.dumper)

    def dump_str(self, obj: Any) -> str:
        """
        Convert the object into YAML and return it as a string

        :param obj: The object to dump
        :returns:      The rendered YAML string
        """
        return dump(obj, Dumper=self.dumper)


class Parser:
    """
    Creates a parser from a registry of conversions from tag to object and back, for example::

        spacial_registry = ConverterRegistry()


        @spacial_registry.register(DataclassConverter, tag="!coord")
        @dataclass
        class Coordinate:
            x: int
            y: int


        # Parse as specific type (validates the result is a coordinate)
        spacial_parser = Parser(spacial_registry)
        spacial_parser(Coordinate).parse_str(...)

        # Parse as any registered type
        spacial_parser.parse_str(...)

    """

    def __init__(
        self,
        registry: ConverterRegistry | None = None,
        implicit_converter: ImplicitConverter | None = None,
    ):
        class _Loader(Loader):
            ...

        class _Dumper(Dumper):
            ...

        self.loader = _Loader
        self.dumper = _Dumper

        # Bind a primitive converter
        reg_implicit_converter = registry and registry._implicit_converter
        if implicit_converter and reg_implicit_converter:
            raise ValueError(
                "Both registry and parser specify"
                " primitive converter, but only one can"
                " be specified!"
            )
        implicit_converter = implicit_converter or reg_implicit_converter
        if implicit_converter is None:
            implicit_converter = StrictImplicitConverter()

        implicit_converter.bind_loader(self.loader)
        implicit_converter.bind_dumper(self.dumper)

        if registry is not None:
            for tag, typ, converter, infer in registry:
                self.register(converter, tag=tag, infer=infer)(typ)

    @overload
    def register(
        self,
        converter_convertable: type[Converter[_Convertable, Self]],
        *,
        tag: str | None = None,
        infer: bool = False,
    ) -> Callable[[type[_Convertable]], type[_Convertable]]:
        ...

    @overload
    def register(
        self,
        converter_convertable: type[_Convertable],
        *,
        tag: str | None = None,
        infer: bool = False,
    ) -> Callable[[type[Converter[_Convertable, Self]]], type[Converter[_Convertable, Self]]]:
        ...

    def register(self, converter_convertable, *, tag: str | None = None, infer: bool = False):
        """
        Register a object for parsing with this parser object.

        :param tag: The yaml tag to register as (!ClassName otherwise)
        """

        def wrap(convertable_converter, /):
            if issubclass(converter_convertable, Converter):
                converter = converter_convertable
                convertable = convertable_converter
            else:
                convertable = converter_convertable
                converter = convertable_converter
            inner_tag = f"!{convertable.__name__}" if tag is None else tag
            converter_inst = converter(tag=inner_tag, typ=convertable, infer=infer)
            converter_inst.bind_loader(self.loader)
            converter_inst.bind_dumper(self.dumper)
            return convertable_converter

        return wrap

    def __call__(self, typ: type[_Convertable]) -> ObjectParser[_Convertable]:
        """
        Create a parser for a specific object

        :param dc:   object to parse as
        :returns:    object Parser
        """
        return ObjectParser(typ, loader=self.loader, dumper=self.dumper)

    def parse(self, path: Path | TextIO) -> Any:
        """
        Parse a YAML file from disk and return the object it contains.

        :param path: Path to the YAML file to parse
        :returns:    Parsed dataclass object
        """
        return self(None).parse(path)

    def parse_str(self, data: str) -> Any:
        """
        Parse a YAML string and return the object it contains.

        :param data: YAML string
        :returns:    Parsed dataclass object
        """
        return self(None).parse_str(data)

    def dump(self, obj: Any, path: Path | TextIO) -> None:
        """
        Dump an object to YAML and write it to the path or file handle
        provided.

        :param obj:  The object to dump
        :param path: Where to write the YAML to
        """
        self(object).dump(obj, path)

    def dump_str(self, obj: Any) -> str:
        """
        Convert the dataclass into YAML and return it as a string

        :param obj: The object to dump
        :returns:   The rendered YAML string
        """
        return self(object).dump_str(obj)


def SimpleParser(  # noqa: N802
    typ: type[_Convertable],
    Converter: type[Converter[_Convertable, Parser]],  # noqa: N803
) -> ObjectParser[_Convertable]:
    """
    Create a parser for a specific object
    """
    parser = Parser()
    parser.register(Converter)(typ)
    return parser(typ)
