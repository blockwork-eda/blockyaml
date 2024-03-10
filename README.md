# blockyaml

Blockyaml is a wrapper around PyYAML which aims to make conversion between YAML and Python objects easier and safer. It was originally created as part of [Blockwork](https://github.com/blockwork-eda/blockwork) but has been separated out for re-use.

## Simple Usage

YAML can be parsed from strings or files.

```python
from blockyaml import Parser

a_dict = Parser().parse_str("""
  key0: val0,
  key1: val1
""")
a_yaml_str = parser.dump_str(a_dict)

result = parser.parse(Path('my/yaml/file.yaml'))
parser.dump(result, Path('my/yaml/file_copy.yaml'))
```

Additional YAML `!Tags` can be converted by by registering a type and a converter with a parser. A simple converter can be written with just a few lines of python:

```python
from blockyaml import Parser, Converter

myparser = Parser()

class Rect:
  def __init__(self, x, y)
    self.x = x
    self.y = y

@parser.register(Rect)
class RectConverter(Converter):
    def construct_mapping(self, loader, node):
        mapping = loader.construct_mapping(node, deep=True)
        return Rect(x=mapping['x'], y=mapping['y'])

    def represent_node(self, dumper, value):
        return dumper.represent_mapping(self.tag, { 'x': value.x, 'y': value.y})

# This syntax of calling the parser with a type asserts the type of the top level object
rect = parser(Rect).parse_str("""
!Rect
x: 2
y: 4
""")
```

A dataclass converter is built-in and has additional checking that all fields are specified and no extra fields are set.

```python
from blockyaml import Parser, DataclassConverter
from dataclasses import dataclass

myparser = Parser()

@myparser.register(DataclassConverter)
@dataclass
class Date:
    month: str
    week: int
    day: int = 0

print(myparser.parse_str("""
!Date
month: June
week: 1
"""))
#> Date(week=1, month='June', day=0)
```

### Additional Checking for Gotchas

Duplicate keys in mappings:

```python
from blockyaml import Parser

Parser().parse_str("""
  key0: val0,
  key0: val1 # NOTE THE DUPLICATE KEY HERE
""")
#> blockyaml.converters.YamlConstructorError: Duplicate key 'key0' detected in mapping
#>   in "<unicode string>", line 2, column 3
```

Non True/False booleans:

```python
from blockyaml import Parser
Parser().parse_str("no")
#> blockyaml.converters.YamlConstructorError: Unsafe bool 'no' detected. Use `true` or `false` for
#> bools, or quote if it is intended to be a string.
#>   in "<unicode string>", line 1, column 1
```
