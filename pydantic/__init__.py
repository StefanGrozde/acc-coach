from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Self, get_origin, get_type_hints

__version__ = "2.0.0"


class _UndefinedType:
    pass


PydanticUndefined = _UndefinedType()


@dataclass(frozen=True)
class FieldInfo:
    default: Any = PydanticUndefined
    default_factory: Callable[[], Any] | None = None


def Field(*, default: Any = PydanticUndefined, default_factory: Callable[[], Any] | None = None) -> FieldInfo:
    if default is not PydanticUndefined and default_factory is not None:
        raise ValueError("Field default and default_factory are mutually exclusive")
    return FieldInfo(default=default, default_factory=default_factory)


class BaseModel:
    model_config: ClassVar[dict[str, Any]] = {}

    def __init__(self, **data: Any) -> None:
        annotations = self._field_annotations()
        values: dict[str, Any] = {}
        for name in annotations:
            if name in data:
                values[name] = data.pop(name)
                continue
            if name in type(self).__dict__:
                default_value = type(self).__dict__[name]
                if isinstance(default_value, FieldInfo):
                    if default_value.default_factory is not None:
                        values[name] = default_value.default_factory()
                    elif default_value.default is not PydanticUndefined:
                        values[name] = default_value.default
                    else:
                        raise TypeError(f"Missing required field: {name}")
                    continue
                values[name] = default_value
            else:
                raise TypeError(f"Missing required field: {name}")
        for key, value in values.items():
            object.__setattr__(self, key, value)
        for key, value in data.items():
            object.__setattr__(self, key, value)

    def model_dump(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self._field_annotations()}

    @classmethod
    def model_validate(cls, data: Any) -> Self:
        if isinstance(data, cls):
            return data
        if isinstance(data, dict):
            return cls(**data)
        raise TypeError(f"Cannot validate {type(data)!r} as {cls.__name__}")

    def __repr__(self) -> str:
        fields = ", ".join(f"{name}={getattr(self, name)!r}" for name in self._field_annotations())
        return f"{type(self).__name__}({fields})"

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.model_dump() == other.model_dump()

    @classmethod
    def _field_annotations(cls) -> dict[str, Any]:
        annotations = get_type_hints(cls, include_extras=True)
        return {name: hint for name, hint in annotations.items() if get_origin(hint) is not ClassVar}
