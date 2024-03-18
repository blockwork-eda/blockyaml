try:
    from yaml import CSafeDumper as Dumper
except ImportError:
    from yaml import SafeDumper as Dumper
from yaml import CollectionNode, MappingNode, Node, ScalarNode, SequenceNode
from yaml.representer import BaseRepresenter as Representer

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
    )
)
