"""Deterministic parsers for structured artifacts."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import sqlparse
import yaml

TreeSitterLanguage = Literal["prisma", "typescript"]
ParserFactory = Callable[[TreeSitterLanguage], Any]

try:
    from tree_sitter_language_pack import get_parser as _get_parser
except ImportError:  # pragma: no cover - dependency is locked for runtime use
    get_parser: ParserFactory | None = None
else:  # pragma: no cover - exercised through concrete parser calls
    get_parser = cast(ParserFactory, _get_parser)


@dataclass(slots=True)
class SchemaEntity:
    name: str
    entity_type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SchemaRelationship:
    source: str
    target: str
    relationship_type: str
    evidence_text: str = ""


_CREATE_TABLE_START_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<table>[A-Za-z_][\w.]*)\s*\(",
    re.IGNORECASE,
)
_COLUMN_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s+([A-Za-z_][\w() ,\[\]]*)", re.IGNORECASE)
_INLINE_FK_RE = re.compile(
    r"([A-Za-z_][\w]*)\s+"
    r"[A-Za-z_][\w() ,\[\]]*REFERENCES\s+"
    r"([A-Za-z_][\w.]*)\s*\(\s*([A-Za-z_][\w]*)\s*\)",
    re.IGNORECASE,
)
_ALTER_FK_RE = re.compile(
    r"ALTER\s+TABLE\s+([A-Za-z_][\w.]*)\s+ADD\s+(?:CONSTRAINT\s+[A-Za-z_][\w]*\s+)?FOREIGN\s+KEY\s*\(\s*([A-Za-z_][\w]*)\s*\)\s+REFERENCES\s+([A-Za-z_][\w.]*)\s*\(\s*([A-Za-z_][\w]*)\s*\)",
    re.IGNORECASE | re.DOTALL,
)
_DRIZZLE_TABLE_FUNCTIONS = {"pgTable", "mysqlTable", "sqliteTable"}
_PRISMA_MODEL_BLOCK_RE = re.compile(
    r"model\s+(?P<name>[A-Za-z_][\w]*)\s*\{(?P<body>.*?)\}",
    re.DOTALL,
)
_PRISMA_FIELD_RE = re.compile(
    r"^(?P<field>[A-Za-z_][\w]*)\s+(?P<type>[A-Za-z_][\w\[\]\?]*)",
)
_PRISMA_RELATION_FIELDS_RE = re.compile(r"fields:\s*\[\s*([A-Za-z_][\w]*)\s*\]")
_PRISMA_RELATION_REFS_RE = re.compile(r"references:\s*\[\s*([A-Za-z_][\w]*)\s*\]")
_DRIZZLE_TABLE_RE = re.compile(
    r"(?:export\s+const\s+[A-Za-z_][\w]*\s*=\s*)?"
    r"(?P<fn>pgTable|mysqlTable|sqliteTable)"
    r"\(\s*['\"](?P<table>[^'\"]+)['\"]\s*,\s*\{(?P<body>.*?)\}\s*\)",
    re.DOTALL,
)
_DRIZZLE_COLUMN_RE = re.compile(
    r"^(?P<name>[A-Za-z_][\w]*)\s*:\s*(?P<expr>.+?)(?:,)?$",
)
_DRIZZLE_BASE_TYPE_RE = re.compile(r"([A-Za-z_][\w]*)\s*\(")
_DRIZZLE_REFERENCE_RE = re.compile(
    r"references\s*\(\s*\(\)\s*=>\s*([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)\s*\)",
)


def _iter_create_table_blocks(content: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for match in _CREATE_TABLE_START_RE.finditer(content):
        table_name = match.group("table").split(".")[-1]
        depth = 1
        body_start = match.end()
        index = body_start
        while index < len(content) and depth > 0:
            char = content[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        if depth == 0:
            blocks.append((table_name, content[body_start : index - 1]))
    return blocks


def _node_text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _iter_descendants(node):
    yield node
    for child in node.children:
        yield from _iter_descendants(child)


def _named_children(node):
    return list(getattr(node, "named_children", []))


def _string_value(source: bytes, node) -> str | None:
    if node is None or node.type != "string":
        return None
    text = _node_text(source, node)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"', "`"}:
        return text[1:-1]
    return text


def _get_ast_parser(language: TreeSitterLanguage) -> Any | None:
    if get_parser is None:
        return None
    try:
        return get_parser(language)
    except Exception:
        return None


def parse_sql(content: str) -> tuple[list[SchemaEntity], list[SchemaRelationship]]:
    if not content.strip():
        return [], []

    sqlparse.parse(content)

    entities: list[SchemaEntity] = []
    relationships: list[SchemaRelationship] = []

    for table_name, body in _iter_create_table_blocks(content):
        entities.append(SchemaEntity(name=table_name, entity_type="table"))

        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line or line.upper().startswith(
                ("PRIMARY", "UNIQUE", "CHECK", "CONSTRAINT", "FOREIGN")
            ):
                continue
            column_match = _COLUMN_RE.match(line)
            if not column_match:
                continue
            column_name = column_match.group(1)
            column_type = column_match.group(2).strip()
            entities.append(
                SchemaEntity(
                    name=f"{table_name}.{column_name}",
                    entity_type="column",
                    properties={"table": table_name, "column": column_name, "type": column_type},
                )
            )

        for fk_match in _INLINE_FK_RE.finditer(body):
            relationships.append(
                SchemaRelationship(
                    source=f"{table_name}.{fk_match.group(1)}",
                    target=f"{fk_match.group(2).split('.')[-1]}.{fk_match.group(3)}",
                    relationship_type="foreign_key",
                    evidence_text=fk_match.group(0).strip(),
                )
            )

    for fk_match in _ALTER_FK_RE.finditer(content):
        relationships.append(
            SchemaRelationship(
                source=f"{fk_match.group(1).split('.')[-1]}.{fk_match.group(2)}",
                target=f"{fk_match.group(3).split('.')[-1]}.{fk_match.group(4)}",
                relationship_type="foreign_key",
                evidence_text=fk_match.group(0).strip(),
            )
        )

    return entities, relationships


def _normalize_prisma_type(type_text: str) -> str:
    return type_text.rstrip("?").removesuffix("[]")


def _extract_prisma_relation_fields(attribute_node, source: bytes) -> tuple[str | None, str | None]:
    source_field: str | None = None
    target_field: str | None = None
    children = attribute_node.children
    for index, child in enumerate(children):
        text = _node_text(source, child)
        if text == "fields":
            for next_child in children[index + 1 :]:
                if next_child.type == "identifier":
                    source_field = _node_text(source, next_child)
                    break
        if text == "references":
            for next_child in children[index + 1 :]:
                if next_child.type == "identifier":
                    target_field = _node_text(source, next_child)
                    break
    return source_field, target_field


def parse_prisma(content: str) -> tuple[list[SchemaEntity], list[SchemaRelationship]]:
    if not content.strip():
        return [], []

    parser = _get_ast_parser("prisma")
    if parser is None:
        return _parse_prisma_fallback(content)

    source = content.encode("utf-8")
    tree = parser.parse(source)
    entities: list[SchemaEntity] = []
    relationships: list[SchemaRelationship] = []

    for node in tree.root_node.children:
        if node.type != "model_block":
            continue

        named = _named_children(node)
        if len(named) < 2 or named[0].type != "identifier":
            continue
        model_name = _node_text(source, named[0])
        entities.append(SchemaEntity(name=model_name, entity_type="model"))

        for child in node.children:
            if child.type != "model_field":
                continue
            field_children = _named_children(child)
            if len(field_children) < 2:
                continue
            field_name_node = field_children[0]
            field_type_node = field_children[1]
            if field_name_node.type != "identifier" or field_type_node.type != "field_type":
                continue

            field_name = _node_text(source, field_name_node)
            field_type = _normalize_prisma_type(_node_text(source, field_type_node))
            entities.append(
                SchemaEntity(
                    name=f"{model_name}.{field_name}",
                    entity_type="field",
                    properties={"model": model_name, "type": field_type},
                )
            )

            for attribute in child.children:
                if attribute.type != "model_single_attribute":
                    continue
                attribute_children = _named_children(attribute)
                if not attribute_children:
                    continue
                attribute_name = _node_text(source, attribute_children[0])
                if attribute_name != "relation":
                    continue
                source_field, target_field = _extract_prisma_relation_fields(attribute, source)
                if source_field and target_field:
                    relationships.append(
                        SchemaRelationship(
                            source=f"{model_name}.{source_field}",
                            target=f"{field_type}.{target_field}",
                            relationship_type="relation",
                            evidence_text=_node_text(source, child).strip(),
                        )
                    )

    if not entities:
        return _parse_prisma_fallback(content)
    return entities, relationships


def _extract_drizzle_base_type(node, source: bytes) -> str | None:
    if node is None:
        return None
    if node.type in {"identifier", "property_identifier"}:
        return _node_text(source, node)

    function_node = getattr(node, "child_by_field_name", lambda _name: None)("function")
    if node.type == "call_expression":
        fallback_node = _named_children(node)[0] if _named_children(node) else None
        return _extract_drizzle_base_type(function_node or fallback_node, source)

    if node.type == "member_expression":
        object_node = getattr(node, "child_by_field_name", lambda _name: None)("object")
        if object_node is None and _named_children(node):
            object_node = _named_children(node)[0]
        return _extract_drizzle_base_type(object_node, source)

    for child in _named_children(node):
        base_type = _extract_drizzle_base_type(child, source)
        if base_type:
            return base_type
    return None


def _extract_drizzle_reference(node, source: bytes) -> str | None:
    if node is None:
        return None

    if node.type == "call_expression":
        function_node = getattr(node, "child_by_field_name", lambda _name: None)("function")
        arguments_node = getattr(node, "child_by_field_name", lambda _name: None)("arguments")
        if function_node is not None and function_node.type == "member_expression":
            property_node = getattr(function_node, "child_by_field_name", lambda _name: None)(
                "property"
            )
            if property_node is None and _named_children(function_node):
                property_node = _named_children(function_node)[-1]
            if property_node is not None and _node_text(source, property_node) == "references":
                if arguments_node is not None:
                    for argument in _named_children(arguments_node):
                        if argument.type == "arrow_function":
                            body_getter = getattr(
                                argument,
                                "child_by_field_name",
                                lambda _name: None,
                            )
                            body_node = body_getter("body")
                            if body_node is None and _named_children(argument):
                                body_node = _named_children(argument)[-1]
                            if body_node is not None:
                                return _node_text(source, body_node)
        for child in _named_children(node):
            target = _extract_drizzle_reference(child, source)
            if target:
                return target

    for child in _named_children(node):
        target = _extract_drizzle_reference(child, source)
        if target:
            return target
    return None


def parse_drizzle(content: str) -> tuple[list[SchemaEntity], list[SchemaRelationship]]:
    if not content.strip():
        return [], []

    parser = _get_ast_parser("typescript")
    if parser is None:
        return _parse_drizzle_fallback(content)

    source = content.encode("utf-8")
    tree = parser.parse(source)
    entities: list[SchemaEntity] = []
    relationships: list[SchemaRelationship] = []

    for node in _iter_descendants(tree.root_node):
        if node.type != "call_expression":
            continue
        function_node = getattr(node, "child_by_field_name", lambda _name: None)("function")
        arguments_node = getattr(node, "child_by_field_name", lambda _name: None)("arguments")
        if function_node is None or arguments_node is None:
            continue
        function_name = _node_text(source, function_node)
        if function_name not in _DRIZZLE_TABLE_FUNCTIONS:
            continue

        args = _named_children(arguments_node)
        if len(args) < 2:
            continue
        table_name = _string_value(source, args[0])
        columns_object = args[1] if args[1].type == "object" else None
        if not table_name or columns_object is None:
            continue

        entities.append(
            SchemaEntity(
                name=table_name,
                entity_type="table",
                properties={"dialect": "drizzle"},
            )
        )

        for pair in columns_object.children:
            if pair.type != "pair":
                continue
            pair_children = _named_children(pair)
            if len(pair_children) < 2:
                continue
            key_node, value_node = pair_children[0], pair_children[-1]
            if key_node.type not in {"property_identifier", "string"}:
                continue
            column_name = (
                _string_value(source, key_node)
                if key_node.type == "string"
                else _node_text(source, key_node)
            )
            if not column_name:
                continue
            column_type = _extract_drizzle_base_type(value_node, source) or "unknown"
            entities.append(
                SchemaEntity(
                    name=f"{table_name}.{column_name}",
                    entity_type="column",
                    properties={
                        "table": table_name,
                        "column": column_name,
                        "type": column_type,
                        "dialect": "drizzle",
                    },
                )
            )
            target = _extract_drizzle_reference(value_node, source)
            if target:
                relationships.append(
                    SchemaRelationship(
                        source=f"{table_name}.{column_name}",
                        target=target,
                        relationship_type="relation",
                        evidence_text=_node_text(source, pair).strip(),
                    )
                )

    if not entities:
        return _parse_drizzle_fallback(content)
    return entities, relationships


def _parse_prisma_fallback(content: str) -> tuple[list[SchemaEntity], list[SchemaRelationship]]:
    entities: list[SchemaEntity] = []
    relationships: list[SchemaRelationship] = []

    for match in _PRISMA_MODEL_BLOCK_RE.finditer(content):
        model_name = match.group("name")
        body = match.group("body")
        entities.append(SchemaEntity(name=model_name, entity_type="model"))

        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//") or line.startswith("@@"):
                continue
            field_match = _PRISMA_FIELD_RE.match(line)
            if field_match is None:
                continue

            field_name = field_match.group("field")
            field_type = _normalize_prisma_type(field_match.group("type"))
            entities.append(
                SchemaEntity(
                    name=f"{model_name}.{field_name}",
                    entity_type="field",
                    properties={"model": model_name, "type": field_type},
                )
            )

            source_field_match = _PRISMA_RELATION_FIELDS_RE.search(line)
            target_field_match = _PRISMA_RELATION_REFS_RE.search(line)
            if source_field_match and target_field_match:
                relationships.append(
                    SchemaRelationship(
                        source=f"{model_name}.{source_field_match.group(1)}",
                        target=f"{field_type}.{target_field_match.group(1)}",
                        relationship_type="relation",
                        evidence_text=line,
                    )
                )

    return entities, relationships


def _parse_drizzle_fallback(content: str) -> tuple[list[SchemaEntity], list[SchemaRelationship]]:
    entities: list[SchemaEntity] = []
    relationships: list[SchemaRelationship] = []

    for match in _DRIZZLE_TABLE_RE.finditer(content):
        table_name = match.group("table")
        body = match.group("body")
        entities.append(
            SchemaEntity(
                name=table_name,
                entity_type="table",
                properties={"dialect": "drizzle"},
            )
        )

        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            column_match = _DRIZZLE_COLUMN_RE.match(line)
            if column_match is None:
                continue

            column_name = column_match.group("name")
            expr = column_match.group("expr")
            base_type_match = _DRIZZLE_BASE_TYPE_RE.search(expr)
            column_type = base_type_match.group(1) if base_type_match else "unknown"
            entities.append(
                SchemaEntity(
                    name=f"{table_name}.{column_name}",
                    entity_type="column",
                    properties={
                        "table": table_name,
                        "column": column_name,
                        "type": column_type,
                        "dialect": "drizzle",
                    },
                )
            )

            ref_match = _DRIZZLE_REFERENCE_RE.search(expr)
            if ref_match:
                relationships.append(
                    SchemaRelationship(
                        source=f"{table_name}.{column_name}",
                        target=f"{ref_match.group(1)}.{ref_match.group(2)}",
                        relationship_type="relation",
                        evidence_text=line,
                    )
                )

    return entities, relationships


def _collect_refs(obj: object, refs: list[str]) -> None:
    if isinstance(obj, dict):
        ref = obj.get("$ref")
        if isinstance(ref, str):
            refs.append(ref)
        for value in obj.values():
            _collect_refs(value, refs)
    elif isinstance(obj, list):
        for value in obj:
            _collect_refs(value, refs)


def parse_openapi(spec: dict[str, Any]) -> tuple[list[SchemaEntity], list[SchemaRelationship]]:
    entities: list[SchemaEntity] = []
    relationships: list[SchemaRelationship] = []

    paths = spec.get("paths", {})
    if isinstance(paths, dict):
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, details in methods.items():
                if method.lower() not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "options",
                    "head",
                }:
                    continue
                endpoint_name = f"{method.upper()} {path}"
                entities.append(
                    SchemaEntity(
                        name=endpoint_name,
                        entity_type="endpoint",
                        properties={"method": method.upper(), "path": path},
                    )
                )
                refs: list[str] = []
                _collect_refs(details, refs)
                for ref in refs:
                    relationships.append(
                        SchemaRelationship(
                            source=endpoint_name,
                            target=ref.split("/")[-1],
                            relationship_type="uses",
                            evidence_text=ref,
                        )
                    )

    components = spec.get("components", {})
    schemas = components.get("schemas", {}) if isinstance(components, dict) else {}
    if isinstance(schemas, dict):
        for name, payload in schemas.items():
            if not isinstance(payload, dict):
                continue
            entities.append(
                SchemaEntity(
                    name=name,
                    entity_type="schema",
                    properties={"type": payload.get("type", "object")},
                )
            )

    return entities, relationships


def extract_schema_intelligence(
    content: str,
    extension: str,
) -> tuple[list[SchemaEntity], list[SchemaRelationship]]:
    normalized_ext = extension.lower()
    if normalized_ext == ".sql":
        return parse_sql(content)
    if normalized_ext == ".prisma":
        return parse_prisma(content)
    if normalized_ext in {".ts", ".tsx", ".js", ".jsx"}:
        return parse_drizzle(content)
    if normalized_ext in {".yaml", ".yml", ".json"}:
        try:
            parsed = json.loads(content) if normalized_ext == ".json" else yaml.safe_load(content)
        except (json.JSONDecodeError, yaml.YAMLError):
            return [], []
        if isinstance(parsed, dict) and ("openapi" in parsed or "swagger" in parsed):
            return parse_openapi(parsed)
    return [], []
