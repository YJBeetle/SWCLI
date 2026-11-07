"""Generate SDK methods/models from the public catalog. Run --check in CI."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import keyword
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
# The generator is installed in scripts/dev; no installed SWCLI dependency.
if (ROOT / "src/swcli").is_dir():
    sys.path.insert(0, str(ROOT / "src"))
from swcli.operation_schemas import OPERATION_CATALOG
from swcli.result_schemas import DOCUMENT, ARTIFACT, LEASE


def camel(value):
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[^a-zA-Z0-9]+", value) if part)


def identifier(value):
    value = value.replace("-", "_")
    if not value.isidentifier() or keyword.iskeyword(value):
        raise ValueError("Unsupported SDK identifier: " + value)
    return value


def parameter_variants(schema):
    """Extract complete object alternatives, never partial allOf conditions."""
    for constraint in schema.get("allOf", []):
        variants = constraint.get("oneOf", [])
        if variants and all(
                part.get("type") == "object"
                and part.get("additionalProperties") is False
                and set(part.get("properties", {})) == set(schema.get("properties", {}))
                and set(part.get("required", [])) == set(schema.get("required", []))
                for part in variants):
            return variants
    return []


class Models:
    def __init__(self):
        self.lines = []
        self.seen = {}
        self.names = set()
        self.precise_objects = False

    def unique(self, name):
        candidate, suffix = name, 2
        while candidate in self.names:
            candidate, suffix = name + str(suffix), suffix + 1
        self.names.add(candidate)
        return candidate

    def union(self, values):
        values = list(dict.fromkeys(values))
        return values[0] if len(values) == 1 else "Union[" + ", ".join(values) + "]"

    def type(self, schema, name):
        if not schema or schema is True:
            return "JSONValue"
        if schema is False:
            raise ValueError("Uninhabited schema needs an explicit SDK mapping: " + name)
        variants = parameter_variants(schema)
        if variants:
            return self.union([self.type(part, name + "Variant" + str(i + 1))
                               for i, part in enumerate(variants)])
        if "const" in schema:
            value = schema["const"]
            if value is None:
                return "None"
            if isinstance(value, (str, int, bool)):
                return "Literal[" + repr(value) + "]"
            return "float"
        if "enum" in schema:
            values = schema["enum"]
            if all(v is not None and isinstance(v, (str, int, bool)) for v in values):
                return "Literal[" + ", ".join(repr(v) for v in values) + "]"
            return self.union([self.type({"const": v}, name) for v in values])
        for key in ("anyOf", "oneOf"):
            if key in schema:
                return self.union([self.type(part, name + "Variant" + str(i + 1)) for i, part in enumerate(schema[key])])
        kind = schema.get("type")
        if isinstance(kind, list):
            return self.union([self.type(dict(schema, type=k), name) for k in kind])
        if kind == "array":
            if schema.get("prefixItems") and schema.get("items") is False:
                # JSON arrays remain lists; exact order/length is runtime checked.
                return "List[" + self.union([self.type(part, name + "Item" + str(i + 1))
                                             for i, part in enumerate(schema["prefixItems"])]) + "]"
            return "List[" + self.type(schema.get("items", {}), name + "Item") + "]"
        if kind == "object":
            properties = schema.get("properties", {})
            invalid_keys = any(not k.isidentifier() or keyword.iskeyword(k) for k in properties)
            if ((not properties and schema.get("additionalProperties") is not False)
                    or (invalid_keys and (not self.precise_objects or set(properties) != set(schema.get("required", []))))):
                additional = schema.get("additionalProperties", {})
                return "Dict[str, " + self.type(additional if isinstance(additional, dict) else {}, name + "Value") + "]"
            canonical = deepcopy(schema)
            for key in ("$id", "$schema", "title", "description"):
                canonical.pop(key, None)
            fingerprint = json.dumps(canonical, sort_keys=True)
            if fingerprint in self.seen:
                return self.seen[fingerprint]
            name = self.unique(name)
            self.seen[fingerprint] = name
            fields = [(key, self.type(value, name + camel(key))) for key, value in properties.items()]
            if invalid_keys:
                self.lines.extend([f'{name} = TypedDict({name!r}, {{',
                    *[f'    {key!r}: {typ},' for key, typ in fields], '})', '', ''])
                return name
            if not fields:
                self.lines.extend([f"class {name}(TypedDict):", "    pass", "", ""])
                return name
            required = set(schema.get("required", []))
            mandatory = [(key, typ) for key, typ in fields if key in required]
            optional = [(key, typ) for key, typ in fields if key not in required]
            if mandatory:
                base = self.unique("_" + name + "Required") if optional else name
                self.lines.extend([f"class {base}(TypedDict):", *[f"    {key}: {typ}" for key, typ in mandatory], "", ""])
            if optional:
                base = base if mandatory else "TypedDict"
                self.lines.extend([f"class {name}({base}, total=False):", *[f"    {key}: {typ}" for key, typ in optional], "", ""])
            return name
        if kind in ("string", "integer", "number", "boolean", "null"):
            return {"string": "str", "integer": "int", "number": "float", "boolean": "bool", "null": "None"}[kind]
        if kind is not None:
            raise ValueError("Unknown schema type: " + str(kind))
        # A schema document or intentionally open JSON extension, not Any.
        return "JSONValue"

    def exported(self, schema, name):
        actual = self.type(schema, name)
        if actual != name:
            self.lines.extend([f"{name} = {actual}", "", ""])
        return name


def render():
    models = Models()
    for schema, name in ((DOCUMENT, "DocumentState"), (ARTIFACT, "Artifact"), (LEASE, "LeaseState")):
        models.exported(schema, name)
    contracts = {}
    for name, spec in OPERATION_CATALOG.items():
        stem = camel(name)
        # Keep existing operation model contracts stable; these new snapshots
        # require typed dotted keys rather than the legacy open dictionary.
        models.precise_objects = name in {
            "document.annotation-font", "document.annotation-font-set",
            "document.display-options", "document.display-option-set",
            "document.drafting-standard", "document.drafting-standard-set",
        }
        contracts[name] = (models.exported(spec.parameters, stem + "Parameters"),
                           models.exported(spec.result, stem + "Result"))
    # Preserve the new public font snapshot alias when an earlier operation
    # already generated the structurally identical shared font TypedDict.
    models.exported(OPERATION_CATALOG["document.annotation-font"].result["properties"]["font"],
                    "DocumentAnnotationFontResultFont")
    model_text = ('"""Generated from operation/result schemas; edit scripts/dev/generate-sdk.py instead."""\n\n'
        'from typing import Dict, List, Literal, TypedDict, Union\nfrom .runtime import JSONValue\n\n\n' + "\n".join(models.lines))
    groups = {}
    for name in OPERATION_CATALOG:
        pieces = name.split(".")
        groups.setdefault(tuple(pieces[:-1]), []).append(name)
    namespaces = set(groups)
    for namespace in list(namespaces):
        for i in range(1, len(namespace)):
            namespaces.add(namespace[:i])
    lines = ['"""Generated typed operation methods; regenerate from the public catalog."""',
        'from __future__ import annotations', '',
        'from typing import Dict, List, Literal, Optional, Protocol, Union, cast, overload',
        'from . import models',
        'from .runtime import JSONValue, Response, UNSET, Unset', '', '',
        'class Dispatcher(Protocol):',
        '    def _execute(self, operation: str, parameters: Optional[Dict[str, object]] = None, *, request_id: Optional[str] = None, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None) -> Response[JSONValue]: ...', '', '']
    for group in sorted(namespaces, key=lambda x: (-len(x), x)):
        klass = camel(".".join(group)) + "Operations"
        lines.extend([f'class {klass}:', '    def __init__(self, client: Dispatcher) -> None:', '        self._client = client'])
        for child in sorted(ns for ns in namespaces if len(ns) == len(group) + 1 and ns[:-1] == group):
            lines.append(f'        self.{identifier(child[-1])} = {camel(".".join(child))}Operations(client)')
        lines.append('')
        for name in groups.get(group, []):
            spec = OPERATION_CATALOG[name]
            required = spec.parameters.get('required', [])
            fields = spec.parameters.get('properties', {})
            parts, assignments = [], []
            for key in list(required) + [k for k in fields if k not in required]:
                typ = models.type(fields[key], camel(name) + 'Parameters' + camel(key))
                # Refer to exported named models; primitives/imported typing stay literal.
                for model in sorted(models.names, key=len, reverse=True):
                    typ = re.sub(r'(?<![A-Za-z0-9_.])' + re.escape(model) + r'(?![A-Za-z0-9_])', 'models.' + model, typ)
                parts.append(f'{identifier(key)}: {typ}' + ('' if key in required else ' |PLACEHOLDER'))
                if key not in required:
                    parts[-1] = f'{identifier(key)}: Union[{typ}, Unset] = UNSET'
                assignments.append((key, key in required))
            context = spec.parameters['x-swcli-context']
            forwarded = []
            for key, mode in context.items():
                if mode == 'forbidden': continue
                typ = 'int' if key == 'expected_update_stamp' else 'str'
                parts.append(f'{key}: {typ}' if mode == 'required' else f'{key}: Optional[{typ}] = None')
                forwarded.append(f'{key}={key}')
            parts.append('request_id: Optional[str] = None')
            result = contracts[name][1]
            for variant in parameter_variants(spec.parameters):
                overload_parts = []
                for key, needed in assignments:
                    typ = models.type(variant['properties'][key], camel(name) + 'Parameters' + camel(key))
                    for model in sorted(models.names, key=len, reverse=True):
                        typ = re.sub(r'(?<![A-Za-z0-9_.])' + re.escape(model) + r'(?![A-Za-z0-9_])', 'models.' + model, typ)
                    overload_parts.append(f'{identifier(key)}: {typ}' if needed else f'{identifier(key)}: Union[{typ}, Unset] = UNSET')
                overload_parts.extend(parts[len(assignments):])
                lines.extend(['    @overload', f'    def {identifier(name.split(".")[-1])}(self, *, ' + ', '.join(overload_parts) + f') -> Response[models.{result}]: ...', ''])
            lines.extend([f'    def {identifier(name.split(".")[-1])}(self, *, ' + ', '.join(parts) + f') -> Response[models.{result}]:',
                f'        """{name}; runtime validation enforces bounds, conditions and context."""',
                '        parameters: Dict[str, object] = {}'])
            for key, needed in assignments:
                if needed:
                    lines.append(f'        parameters[{key!r}] = {key}')
                else:
                    lines.extend([f'        if {key} is not UNSET:', f'            parameters[{key!r}] = {key}'])
            suffix = ', '.join(['request_id=request_id'] + forwarded)
            lines.extend([f'        return cast("Response[models.{result}]", self._client._execute({name!r}, parameters, {suffix}))', '', ''])
    lines.extend(['class GeneratedAPI:', '    def __init__(self) -> None:'])
    for group in sorted(ns for ns in namespaces if len(ns) == 1):
        lines.append(f'        self.{identifier(group[0])} = {camel(group[0])}Operations(self)')
    lines.extend(['', '    def _execute(self, operation: str, parameters: Optional[Dict[str, object]] = None, *, request_id: Optional[str] = None, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None) -> Response[JSONValue]:',
                  '        raise NotImplementedError', ''])
    # All named nested request types were registered while building models.
    return {'models.py': model_text.rstrip() + '\n', '_generated.py': '\n'.join(lines)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    changed = []
    for name, text in render().items():
        path = ROOT / 'src/swcli/sdk' / name
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8') != text:
                changed.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
    if changed:
        parser.error('SDK is out of date; regenerate: ' + ', '.join(changed))


if __name__ == '__main__':
    main()
