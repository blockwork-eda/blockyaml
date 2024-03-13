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

import abc
import sys
from collections.abc import Callable, Iterable
from dataclasses import _MISSING_TYPE, dataclass, fields
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypeVar,
    cast,
    overload,
)

if TYPE_CHECKING:
    from dataclasses import _DataclassT

    from .parsers import Parser

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader

from .types import (
    CollectionNode,
    MappingNode,
    Node,
    Representer,
    ScalarNode,
    SequenceNode,
    YAMLConstructorError,
    YAMLError,
    YAMLRepresenterError,
)


class YAMLConversionError(YAMLError):
    "Error parsing yaml"

    def __init__(self, location: Path | str, msg: str):
        self.location = location
        self.msg = msg

    def __str__(self):
        return f"{self.location}: {self.msg}"


_Convertable = TypeVar("_Convertable")
_Parser = TypeVar(
    "_Parser",
    bound="Parser",
)


class Converter(abc.ABC, Generic[_Convertable, _Parser]):
    """
    Defines how to convert between a yaml tag and a python type, intended
    to be subclassed and used in parser registries. For example::

        class WrapConverter(Converter):
            def construct_scalar(self, loader, node):
                return self.typ(loader.construct_scalar(node))


        wrap_parser = Parser()


        @wrap_parser.register(WrapConverter, tag="!Wrap")
        class Wrapper:
            def __init__(self, content):
                self.content = content


        print(wrap_parser.parse_str("data: !Wrap yum"))
    """

    def __init__(self, *, tag: str, typ: type[_Convertable]):
        self.tag = tag
        self.typ = typ

    def bind_loader(self, loader: type[Loader]):
        self._base_constructor = loader.yaml_constructors.get(self.tag, None)
        loader.yaml_constructors[self.tag] = self.construct

    def bind_dumper(self, dumper: type[Dumper]):
        self._base_representer = dumper.yaml_representers.get(self.typ, None)
        dumper.yaml_representers[self.typ] = self.represent

    def construct(self, loader: Loader, node: Node):
        match node:
            case MappingNode():
                return self.construct_mapping(loader, node)
            case SequenceNode():
                return self.construct_sequence(loader, node)
            case ScalarNode():
                return self.construct_scalar(loader, node)
            case CollectionNode():
                return self.construct_collection(loader, node)
            case _:
                return self.construct_node(loader, node)

    def represent(self, representer: Representer, value: _Convertable):
        return self.represent_node(representer, value)

    def construct_mapping(self, loader: Loader, node: MappingNode) -> _Convertable:
        return self.construct_node(loader, node)

    def construct_sequence(self, loader: Loader, node: SequenceNode) -> _Convertable:
        return self.construct_node(loader, node)

    def construct_scalar(self, loader: Loader, node: ScalarNode) -> _Convertable:
        return self.construct_node(loader, node)

    def construct_collection(self, loader: Loader, node: CollectionNode) -> _Convertable:
        return self.construct_node(loader, node)

    def construct_node(self, loader: Loader, node: Node) -> _Convertable:
        if self._base_constructor:
            return self._base_constructor(loader, node)
        raise NotImplementedError

    def represent_node(self, representer: Representer, value: _Convertable) -> Node:
        if self._base_representer:
            return self._base_representer(representer, value)
        raise NotImplementedError


class PrimitiveConverter(Converter[_Convertable, _Parser]):
    """
    Converter for primitive objects, allows for sanity checks to be
    imposed on the data beyond standard YAML syntax.
    """

    def bind_loader(self, loader: type[Loader]):
        self._base_constructors: dict[str, Callable] = {}
        for tag, constructor in loader.yaml_constructors.items():
            self._base_constructors[tag] = constructor
            loader.yaml_constructors[tag] = self.construct

    def bind_dumper(self, dumper: type[Dumper]):
        self._base_representers: dict[type, Callable] = {}
        for typ, representer in dumper.yaml_representers.items():
            self._base_representers[typ] = representer
            dumper.yaml_representers[typ] = self.represent

    def construct_node(self, loader: Loader, node: Node) -> _Convertable:
        if constructor := self._base_constructors.get(node.tag, None):
            return constructor(loader, node)
        raise YAMLConstructorError(
            f"Got tag `{node.tag}` with no registered"
            " converter. If it is meant to be a string"
            " it requires quotes, otherwise a"
            " converter will need to be registered.",
            context_mark=node.start_mark,
        )

    def represent_node(self, representer: Representer, value: _Convertable) -> _Convertable:
        if base_representer := self._base_representers.get(type(value), None):
            return base_representer(representer, value)
        raise YAMLRepresenterError(
            f"Got type `{type(value)}` without a"
            " registered converter. A converter will"
            " need to be registered."
        )


@dataclass(kw_only=True)
class SensiblePrimitives(PrimitiveConverter[_Convertable, _Parser]):
    """
    Converter for primitive objects with sensible checking by default.
    """

    strict_keys: bool = True
    "Disallow duplicate keys in mappings"
    strict_bools: bool = True
    "Disallow bools other than `true` or `false` (case-insensitive)"
    strict_numbers: bool = True
    "Disallow sexagesimal number (e.g. 42:45)"

    def construct_mapping(self, loader: Loader, node: MappingNode) -> _Convertable:
        if self.strict_keys:
            seen = []
            for key, _ in node.value:
                key = self.construct_node(loader, key)
                if key in seen:
                    raise YAMLConstructorError(
                        f"Duplicate key '{key}' detected in mapping",
                        context_mark=node.start_mark,
                    )
                seen.append(key)
        return super().construct_mapping(loader, node)

    def construct_scalar(self, loader: Loader, node: ScalarNode) -> Any:
        value = super().construct_scalar(loader, node)
        if self.strict_bools:
            if isinstance(value, bool) and node.value.lower() not in ("true", "false"):
                raise YAMLConstructorError(
                    f"Unsafe bool '{node.value}' detected. Use `true` or"
                    " `false` for bools, or quote if it is intended to be"
                    " a string.",
                    context_mark=node.start_mark,
                )
        if self.strict_numbers:
            if isinstance(value, int | float) and ":" in node.value:
                raise YAMLConstructorError(
                    f"Unsafe number '{node.value}' detected. This is"
                    " probably meant to be a string, please quote it.",
                    context_mark=node.start_mark,
                )
        return value


class ConverterRegistry:
    """
    Creates an object with which to register converters which
    can be used to initialise a Parser object.
    """

    def __init__(self, primitive_converter: PrimitiveConverter | None = None):
        self._primitive_converter = primitive_converter
        self._registered_tags: set[str] = set()
        self._registered_typs: set[Any] = set()
        self._registry: list[tuple[str, Any, type[Converter]]] = []

    def __iter__(self):
        yield from self._registry

    @overload
    def register(
        self,
        converter_convertable: type[Converter[_Convertable, "Parser"]],
        *,
        tag: str | None = None,
    ) -> Callable[[type[_Convertable]], type[_Convertable]]:
        ...

    @overload
    def register(
        self,
        converter_convertable: type[_Convertable],
        *,
        tag: str | None = None,
    ) -> Callable[
        [type[Converter[_Convertable, "Parser"]]],
        type[Converter[_Convertable, "Parser"]],
    ]:
        ...

    def register(
        self,
        converter_convertable,
        *,
        tag: str | None = None,
    ):
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

            if inner_tag in self._registered_tags:
                raise RuntimeError(f"Converter already exists for tag `{inner_tag}`")

            if convertable in self._registered_typs:
                raise RuntimeError(f"Converter already exists for type `{convertable}`")

            self._registry.append((inner_tag, convertable, converter))
            return convertable_converter

        return wrap


class YAMLDataclassFieldError(YAMLConversionError):
    "Error parsing YAML Dataclass field"

    def __init__(self, location: str, ex: Exception, field: str | None = None):
        self.field = field
        self.orig_ex = ex
        field_str = "" if self.field is None else f" at field `{self.field}`"
        super().__init__(f"{location}{field_str}", str(ex))


class YAMLDataclassMissingFieldsError(YAMLConversionError):
    def __init__(self, location: str, fields: Iterable[str]):
        self.fields = fields
        super().__init__(location, f"Missing field(s) `{', '.join(map(str, self.fields))}`")


class YAMLDataclassExtraFieldsError(YAMLConversionError):
    def __init__(self, location: str, fields: Iterable[str]):
        self.fields = fields
        super().__init__(location, f"Got extra field(s) `{', '.join(map(str, self.fields))}`")


class DataclassConverter(Converter["_DataclassT", _Parser]):
    def construct_mapping(self, loader: Loader, node: MappingNode) -> "_DataclassT":
        loc = ":".join(
            map(
                str,
                (
                    Path(node.start_mark.name).absolute(),
                    node.start_mark.line,
                    node.start_mark.column,
                ),
            )
        )
        node_dict = cast(dict[str, Any], loader.construct_mapping(node, deep=True))

        # Get some info from the fields
        required_keys = set()
        keys = set()
        for field in fields(self.typ):
            keys.add(field.name)
            if isinstance(field.default, _MISSING_TYPE) and isinstance(
                field.default_factory, _MISSING_TYPE
            ):
                required_keys.add(field.name)

        # Check there are no extra fields provided
        if extra := set(node_dict.keys()) - set(keys):
            raise YAMLDataclassExtraFieldsError(loc, extra)

        # Check there are no missing fields
        missing = set(required_keys) - set(node_dict.keys())
        if missing:
            raise YAMLDataclassMissingFieldsError(loc, missing)

        try:
            # Create the dataclass instance
            instance = self.typ(**node_dict)
        except TypeError as ex:
            # Note, might be nice to add some heuristics to get the location
            # based on the field error
            sys.tracebacklimit = 0
            raise YAMLDataclassFieldError(loc, ex, getattr(ex, "field", None)) from None

        return instance

    def represent_node(self, representer: Representer, value: "_DataclassT") -> Node:
        return representer.represent_mapping(self.tag, value.__dict__)
