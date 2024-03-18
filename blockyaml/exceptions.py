from yaml import YAMLError
from yaml.constructor import ConstructorError as YAMLConstructorError
from yaml.representer import RepresenterError as YAMLRepresenterError


# Registration Errors
class YAMLRegistrationError(YAMLError):
    "Base exception to use for registration errors"


class YAMLRegistrationTypeError(YAMLRegistrationError):
    "Invalid conversion type e.g. `list[str]` not list"


class YAMLRegistrationDuplicateTagError(YAMLRegistrationError):
    "YAML tag already registered"


class YAMLRegistrationDuplicateTypeError(YAMLRegistrationError):
    "YAML type already registered"


class YAMLRegistrationMultipleImplicitError(YAMLRegistrationError):
    "Multiple implicit converters specified"


# Constructor Errors
class YAMLConstructorMissingError(YAMLConstructorError):
    "YAML constructor does not exist for a tag"


class YAMLConstructorNotImplementedError(YAMLConstructorError):
    "YAML constructor exists for tag, but a method this type of object does not"


class YAMLConstructorMultipleImplicitError(YAMLConstructorError):
    "Multiple implicit contstructors exist for type"


class YAMLConstructorInvalidTypeError(YAMLConstructorError):
    "Constructed value doesn't match expected type"


# Representer Errors
class YAMLRepresenterMissingError(YAMLRepresenterError):
    "YAML representer does not exist for a type"


class YAMLRepresenterNotImplementedError(YAMLRepresenterError):
    "YAML representer exists for type, but method is not implemented?"


# Strict Errors
class YAMLStrictConstructorError(YAMLConstructorError):
    "Base exception to use for strict errors"


class YAMLStrictKeyError(YAMLStrictConstructorError):
    "Duplicate key in YAML mapping"


class YAMLStrictBoolError(YAMLStrictConstructorError):
    "Unsafe boolean value e.g. `no` in YAML scalar"


class YAMLStrictNumberError(YAMLStrictConstructorError):
    "Unsafe number value e.g. `23:23` in YAML scalar"
