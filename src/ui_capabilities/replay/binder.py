"""Invocation validation and value binding. Everything fails *before* a
browser action if the invocation does not satisfy the contract."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from ..models.artifact import CapabilityContract, InputValueRef, LiteralValue, ValueType
from ..models.errors import CapabilityError


class InvocationError(CapabilityError):
    pass


class OutputCoercionError(CapabilityError):
    pass


def validate_and_bind(contract: CapabilityContract, provided: dict[str, str]) -> dict[str, str]:
    declared = {spec.name: spec for spec in contract.inputs}
    unknown = set(provided) - set(declared)
    if unknown:
        raise InvocationError(f"unknown input(s): {sorted(unknown)}")
    bound: dict[str, str] = {}
    for name, spec in declared.items():
        if name not in provided or provided[name] == "":
            if spec.required:
                raise InvocationError(f"missing required input {name!r}")
            continue
        raw = provided[name].strip()
        _validate_type(name, raw, spec.type)
        if spec.pattern and not re.fullmatch(spec.pattern, raw):
            raise InvocationError(f"input {name!r} does not match required pattern {spec.pattern!r}")
        if spec.minimum is not None or spec.maximum is not None:
            num = float(raw)
            if spec.minimum is not None and num < spec.minimum:
                raise InvocationError(f"input {name!r} below minimum {spec.minimum}")
            if spec.maximum is not None and num > spec.maximum:
                raise InvocationError(f"input {name!r} above maximum {spec.maximum}")
        bound[name] = raw
    return bound


def _validate_type(name: str, raw: str, value_type: ValueType) -> None:
    try:
        if value_type == "integer":
            int(raw)
        elif value_type == "decimal":
            float(raw)
        elif value_type == "boolean":
            if raw.lower() not in ("true", "false", "1", "0", "yes", "no"):
                raise ValueError
    except ValueError:
        raise InvocationError(f"input {name!r} is not a valid {value_type}") from None


def resolve_value(value: InputValueRef | LiteralValue, bound: dict[str, str]) -> str:
    if isinstance(value, InputValueRef):
        if value.name not in bound:
            raise InvocationError(f"step references input {value.name!r} which was not bound")
        return bound[value.name]
    return str(value.value)


def render_url(template: str, bound: dict[str, str], entry_point: str) -> str:
    rendered = template
    for placeholder in re.findall(r"\{([a-z_][a-z0-9_]*)\}", template):
        if placeholder not in bound:
            raise InvocationError(f"url template references unbound input {placeholder!r}")
        rendered = rendered.replace("{" + placeholder + "}", bound[placeholder])
    if rendered.startswith("http://") or rendered.startswith("https://"):
        return rendered
    entry = urlparse(entry_point)
    return urlunparse((entry.scheme, entry.netloc, rendered.split("?")[0], "", rendered.partition("?")[2], ""))


_MONEY_JUNK = re.compile(r"[$,\s]")


def coerce_output(name: str, raw: str, value_type: ValueType):
    text = raw.strip()
    try:
        if value_type == "decimal":
            return float(_MONEY_JUNK.sub("", text))
        if value_type == "integer":
            return int(_MONEY_JUNK.sub("", text))
        if value_type == "boolean":
            return text.lower() in ("true", "yes", "1")
        return text
    except ValueError:
        raise OutputCoercionError(f"output {name!r}: cannot coerce extracted text to {value_type}") from None
