try:
    from yaml import CSafeLoader as _Loader
except ImportError:
    from yaml import SafeLoader as _Loader

from contextlib import contextmanager
from types import UnionType
from typing import TYPE_CHECKING, Any, ClassVar, get_args, get_origin

if TYPE_CHECKING:
    from .types import CollectionNode, MappingNode, Node, ScalarNode, SequenceNode


def decompose_list_type(typ) -> tuple[tuple[type] | None, tuple[type] | None]:
    if typ is list:
        return (list,), None
    elif get_origin(typ) is list:
        return (list,), get_args(typ)
    elif isinstance(typ, UnionType):
        union_types = ()
        for member_typ in get_args(typ):
            if member_typ is list:
                return (list,), None
            elif get_origin(member_typ) is list:
                union_types += get_args(member_typ)
            else:
                continue
        if union_types:
            return (list,), union_types
    return (typ,), None


def decompose_dict_type(typ) -> tuple[tuple[type] | None, tuple[type] | None, tuple[type] | None]:
    if typ is dict:
        return (dict,), None, None
    elif get_origin(typ) is dict:
        return (dict,), *get_args(typ)
    elif isinstance(typ, UnionType):
        union_key_types = ()
        union_val_types = ()
        for member_typ in get_args(typ):
            if member_typ is dict:
                return (dict,), None, None
            elif get_origin(member_typ) is dict:
                key_type, val_type = get_args(member_typ)
                union_key_types += (key_type,)
                union_val_types += (val_type,)
            else:
                continue
        if union_key_types:
            return (dict,), union_key_types, union_val_types
    return (typ,), None, None


def decompose_scalar_type(typ) -> tuple[type]:
    if isinstance(typ, UnionType):
        union = ()
        for member_typ in get_args(typ):
            origin = get_origin(member_typ) or member_typ
            if origin is dict or origin is list:
                continue
            union += (member_typ,)
        return union
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
        if own_typ is None or isinstance(value, own_typ):
            return value
        if len(own_typ) == 1 and (constructor := self.yaml_type_constructors.get(own_typ[0])):
            return constructor(self, node)
        raise Exception

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
