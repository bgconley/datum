"""Deterministic parsers for structured artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import sqlparse
import yaml


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
_PRISMA_MODEL_RE = re.compile(r"model\s+([A-Za-z_][\w]*)\s*\{(.*?)\}", re.DOTALL)
_PRISMA_FIELD_RE = re.compile(
    r"^\s*([A-Za-z_][\w]*)\s+([A-Za-z_][\w\[\]?]*)\s*(.*?)$",
    re.MULTILINE,
)
_PRISMA_RELATION_RE = re.compile(
    r"@relation\(fields:\s*\[([A-Za-z_][\w]*)\],\s*references:\s*\[([A-Za-z_][\w]*)\]\)"
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


def parse_prisma(content: str) -> tuple[list[SchemaEntity], list[SchemaRelationship]]:
    if not content.strip():
        return [], []

    entities: list[SchemaEntity] = []
    relationships: list[SchemaRelationship] = []

    for model_match in _PRISMA_MODEL_RE.finditer(content):
        model_name = model_match.group(1)
        body = model_match.group(2)
        entities.append(SchemaEntity(name=model_name, entity_type="model"))

        for field_match in _PRISMA_FIELD_RE.finditer(body):
            field_name = field_match.group(1)
            field_type = field_match.group(2).rstrip("?")
            attrs = field_match.group(3)
            if field_name.startswith("//"):
                continue
            entities.append(
                SchemaEntity(
                    name=f"{model_name}.{field_name}",
                    entity_type="field",
                    properties={"model": model_name, "type": field_type},
                )
            )
            relation_match = _PRISMA_RELATION_RE.search(attrs)
            if relation_match:
                relationships.append(
                    SchemaRelationship(
                        source=f"{model_name}.{relation_match.group(1)}",
                        target=f"{field_type.rstrip('[]')}.{relation_match.group(2)}",
                        relationship_type="relation",
                        evidence_text=field_match.group(0).strip(),
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
    if normalized_ext in {".yaml", ".yml", ".json"}:
        try:
            parsed = json.loads(content) if normalized_ext == ".json" else yaml.safe_load(content)
        except (json.JSONDecodeError, yaml.YAMLError):
            return [], []
        if isinstance(parsed, dict) and ("openapi" in parsed or "swagger" in parsed):
            return parse_openapi(parsed)
    return [], []
