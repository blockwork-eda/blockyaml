try:
    from yaml import CSafeLoader as _Loader
except ImportError:
    from yaml import SafeLoader as _Loader

from contextlib import contextmanager
from types import UnionType
from typing import TYPE_CHECKING, Any, ClassVar, Union, get_args, get_origin

from blockyaml.exceptions import (
    YAMLConstructorInvalidTypeError,
    YAMLConstructorMultipleImplicitError,
)

if TYPE_CHECKING:
    from .types import CollectionNode, MappingNode, Node, ScalarNode, SequenceNode


def flatten_type(typ) -> tuple[type]:
    if isinstance(typ, tuple):
        return typ
    if isinstance(typ, UnionType):
        return get_args(typ)
    return (typ,)


def decompose_list_type(typ) -> tuple[tuple[type] | None, tuple[type] | None]:
    if typ is list:
        return (list,), None
    elif get_origin(typ) is list:
        val_typs, *_ = get_args(typ)
        return (list,), Union[val_typs]  # noqa UP007
    elif isinstance(typ, UnionType):
        union_types = ()
        for mem_typ in get_args(typ):
            if mem_typ is list:
                return (list,), None
            elif get_origin(mem_typ) is list:
                mem_val_typs, *_ = get_args(mem_typ)
                union_types += flatten_type(mem_val_typs)
            else:
                continue
        if union_types:
            return (list,), Union[union_types]  # noqa UP007
    return (typ,), None


def decompose_dict_type(typ) -> tuple[tuple[type] | None, tuple[type] | None, tuple[type] | None]:
    if typ is dict:
        return (dict,), None, None
    elif get_origin(typ) is dict:
        key_typs, val_typs = get_args(typ)
        return (dict,), key_typs, val_typs
    elif isinstance(typ, UnionType):
        union_key_types = ()
        union_val_types = ()
        for member_typ in get_args(typ):
            if member_typ is dict:
                return (dict,), None, None
            elif get_origin(member_typ) is dict:
                mem_key_typs, mem_val_typs = get_args(member_typ)
                union_key_types += flatten_type(mem_key_typs)
                union_val_types += flatten_type(mem_val_typs)
            else:
                continue
        if union_key_types:
            return (dict,), Union[union_key_types], Union[union_val_types]  # noqa UP007
    return (typ,), None, None


def decompose_scalar_type(typ) -> tuple[type]:
    if isinstance(typ, UnionType):
        return get_args(typ)
    return (typ,)


class Loader(_Loader):
    yaml_type_constructors: ClassVar = {}

    @classmethod
    @contextmanager
    def expected_type(cls, typ):
        try:
            cls.__document_type__ = typ
            yield
        finally:
            cls.__document_type__ = None

    def construct_object(self, node: "Node", deep: bool = False):
        value = super().construct_object(node, deep)
        own_typ = getattr(node, "__expected_own_type__", None)
        if own_typ is None:
            return value
        constructor_pairs = []
        for typ in own_typ:
            try:
                if isinstance(value, typ):
                    return value
            except TypeError:
                pass
            if (constructor := self.yaml_type_constructors.get(typ, None)) is None:
                continue
            constructor_pairs.append((typ, constructor))
        if len(constructor_pairs) == 1:
            return constructor_pairs[0][1](self, node)
        elif len(constructor_pairs):
            tag_strs = []
            for typ, constructor in constructor_pairs:
                for tag, tag_constructor in self.yaml_constructors.items():
                    if constructor == tag_constructor:
                        tag_strs.append(f"{tag} -> {typ}")
            raise YAMLConstructorMultipleImplicitError(
                None,
                None,
                "Can't determine implicit constructor to use for"
                f" `{type(value)}` as multiple match. Either specify a tag"
                f" explicitely from the options `{', '.join(tag_strs)}` or"
                " update the type.",
                problem_mark=node.start_mark,
            )
        expected_type = getattr(node, "__expected_type__", own_typ)
        raise YAMLConstructorInvalidTypeError(
            None,
            None,
            f"Type `{type(value)}` does not match expected type" f" `{expected_type}`.",
            problem_mark=node.start_mark,
        )

    def construct_mapping(self, node: "MappingNode", deep: bool = False) -> dict:
        expected_type = getattr(node, "__expected_type__", None)
        return self.construct_typed_mapping(node, expected_type, deep)

    def construct_sequence(self, node: "SequenceNode") -> list:
        expected_type = getattr(node, "__expected_type__", None)
        if expected_type is None:
            return super().construct_sequence(node)
        return self.construct_typed_sequence(node, expected_type)

    def construct_scalar(self, node: "ScalarNode") -> Any:
        expected_type = getattr(node, "__expected_type__", None)
        if expected_type is None:
            return super().construct_scalar(node)
        return self.construct_typed_scalar(node, expected_type)

    def construct_collection(self, node: "CollectionNode") -> Any:
        expected_type = getattr(node, "__expected_type__", None)
        if expected_type is None:
            return super().construct_collection(node)
        return self.construct_typed_collection(node, expected_type)

    def construct_document(self, node: "Node") -> Any:
        expected_type = getattr(self, "__document_type__", None)
        if expected_type is not None:
            node.__expected_type__ = expected_type
        return super().construct_document(node)

    def construct_typed_mapping(self, node: "MappingNode", typ: Any, deep: bool) -> dict:
        dict_typ, key_typ, val_typ = decompose_dict_type(typ)

        node.__expected_own_type__ = dict_typ
        for key_node, val_node in node.value:
            key_node.__expected_type__ = key_typ
            val_node.__expected_type__ = val_typ

        return super().construct_mapping(node, deep)

    def construct_fixed_mapping(self, node: "MappingNode", key_typs: Any, deep: bool) -> dict:
        for key_node, value_node in node.value:
            key = super().construct_object(key_node)
            if key not in key_typs:
                raise Exception
            value_node.__expected_type__ = key_typs[key]
        # TODO Check for extra keys?
        value = super().construct_mapping(node, deep)
        return value

    def construct_typed_sequence(self, node: "SequenceNode", typ: Any) -> list:
        list_typ, val_typ = decompose_list_type(typ)

        node.__expected_own_type__ = list_typ
        for val_node in node.value:
            val_node.__expected_type__ = val_typ

        return super().construct_sequence(node)

    def construct_typed_scalar(self, node: "ScalarNode", typ: Any) -> Any:
        scalar_typ = decompose_scalar_type(typ)
        node.__expected_own_type__ = scalar_typ
        return super().construct_scalar(node)

    def construct_typed_collection(self, node: "CollectionNode", typ: Any) -> Any:
        if constructor := self.yaml_type_constructors.get(typ):
            return constructor(self, node)

        value = super().construct_collection(node)
        self.check_type(value, node, typ)
        return value
