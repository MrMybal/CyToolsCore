"""The packaged Draft 2020-12 schemas are the wire contract, not Python classes."""
import copy
import json
from importlib.resources import files
from jsonschema import Draft202012Validator, ValidationError, SchemaError
from .errors import CyToolError


def schema(name):
    return json.loads(files("cytools_core").joinpath("schemas", name + ".schema.json").read_text("utf-8"))


def validate_document(value, name):
    try:
        json.dumps(value, allow_nan=False)
        Draft202012Validator(schema(name)).validate(value)
    except (ValidationError, ValueError, TypeError) as exc:
        raise CyToolError("InvalidDescriptor", getattr(exc,'message',str(exc)), details={"path": list(getattr(exc,'absolute_path',[]))}) from exc
    return value


def _check_schema(node):
    # Never resolve network/file references on behalf of an untrusted manifest.
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("$ref", "$dynamicRef") and (not isinstance(value, str) or not value.startswith("#")):
                raise CyToolError("InvalidDescriptor", "Only local schema references are allowed")
            _check_schema(value)
    elif isinstance(node, list):
        for value in node:
            _check_schema(value)


def validate_manifest(value):
    validate_document(value, "tool")
    if value["schemaVersion"] != 1 or value["protocolVersion"].split(".")[0] != "1":
        raise CyToolError("IncompatibleVersion", "CyTools schema/protocol major version must be 1")
    for group in ("operations", "backends"):
        ids = [item["id"] for item in value.get(group, [])]
        if len(ids) != len(set(ids)):
            raise CyToolError("InvalidDescriptor", f"Duplicate {group} IDs")
    backends = {b["id"] for b in value.get("backends", [])}
    for backend in value.get("backends", []):
        ids = [m["id"] for m in backend.get("models", [])]
        if len(ids) != len(set(ids)):
            raise CyToolError("InvalidDescriptor", "Duplicate model IDs")
    for operation in value["operations"]:
        if not set(operation.get("supportedBackends", [])) <= backends:
            raise CyToolError("InvalidDescriptor", "Operation references an unknown backend")
        for key in ("inputSchema", "outputSchema"):
            document = operation[key]
            _check_schema(document)
            try:
                Draft202012Validator.check_schema(document)
            except SchemaError as exc:
                raise CyToolError("InvalidDescriptor", exc.message) from exc
    return copy.deepcopy(value)


def load_manifest(path):
    with open(path, encoding="utf-8-sig") as source:
        return validate_manifest(json.load(source))


def _defaults(value, spec, root):
    if "$ref" in spec:
        target = root
        for part in (spec["$ref"][2:].split("/") if spec["$ref"] != '#' else []):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        _defaults(value, target, root)
    if isinstance(value, dict):
        for key, child in spec.get("properties", {}).items():
            if key not in value and "default" in child:
                value[key] = copy.deepcopy(child["default"])
            if key in value:
                _defaults(value[key], child, root)
    if isinstance(value, list) and isinstance(spec.get("items"), dict):
        for item in value:
            _defaults(item, spec["items"], root)
    for child in spec.get("allOf", []):
        _defaults(value, child, root)
    if "if" in spec:
        branch = "then" if Draft202012Validator(root).evolve(schema=spec["if"]).is_valid(value) else "else"
        _defaults(value, spec.get(branch, {}), root)


def validate_parameters(value, spec, *, defaults=True):
    result = copy.deepcopy(value)
    try:
        # Reject NaN/Infinity and non-JSON Python objects at every boundary.
        json.dumps(result, allow_nan=False)
        if defaults:
            _defaults(result, spec, spec)
        json.dumps(result, allow_nan=False)
        Draft202012Validator(spec).validate(result)
    except (ValidationError, ValueError, TypeError, RecursionError, KeyError) as exc:
        raise CyToolError("InvalidParameters", str(exc).split("\n")[0]) from exc
    return result
