try:
    from yaml import CSafeDumper as Dumper
except ImportError:
    from yaml import SafeDumper as Dumper
from yaml import CollectionNode, MappingNode, Node, ScalarNode, SequenceNode, YAMLError
from yaml.constructor import ConstructorError as YAMLConstructorError
from yaml.representer import BaseRepresenter as Representer
from yaml.representer import RepresenterError as YAMLRepresenterError

from .loader import Loader

assert all(
    (
        Dumper,
        Loader,
        Representer,
        Node,
        MappingNode,
        SequenceNode,
        ScalarNode,
        CollectionNode,
        YAMLError,
        YAMLConstructorError,
        YAMLRepresenterError,
    )
)
