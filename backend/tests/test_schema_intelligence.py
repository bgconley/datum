"""Tests for schema intelligence parsers."""

from datum.services.schema_intelligence import (
    extract_schema_intelligence,
    parse_drizzle,
    parse_openapi,
    parse_prisma,
    parse_sql,
)


def test_parse_sql_extracts_tables_columns_and_fk():
    entities, relationships = parse_sql(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            email TEXT NOT NULL
        );

        CREATE TABLE sessions (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id)
        );
        """
    )
    assert any(item.entity_type == "table" and item.name == "users" for item in entities)
    assert any(
        item.entity_type == "column" and item.name == "sessions.user_id"
        for item in entities
    )
    assert any(item.relationship_type == "foreign_key" for item in relationships)


def test_parse_prisma_extracts_models_and_relations():
    entities, relationships = parse_prisma(
        """
        model User {
          id    String @id
          posts Post[]
        }

        model Post {
          id       String @id
          author   User   @relation(fields: [authorId], references: [id])
          authorId String
        }
        """
    )
    assert any(item.entity_type == "model" and item.name == "User" for item in entities)
    assert any(item.entity_type == "field" and item.name == "Post.authorId" for item in entities)
    assert any(item.relationship_type == "relation" for item in relationships)


def test_parse_drizzle_extracts_tables_columns_and_relations():
    entities, relationships = parse_drizzle(
        """
        export const orgs = pgTable('orgs', {
          id: uuid('id').primaryKey(),
        })

        export const users = pgTable('users', {
          id: uuid('id').primaryKey(),
          email: text('email').notNull(),
          orgId: uuid('org_id').references(() => orgs.id),
        })
        """
    )
    assert any(item.entity_type == "table" and item.name == "users" for item in entities)
    assert any(
        item.entity_type == "column" and item.name == "users.orgId"
        for item in entities
    )
    assert any(
        item.relationship_type == "relation" and item.target == "orgs.id"
        for item in relationships
    )


def test_parse_openapi_extracts_endpoints_and_refs():
    entities, relationships = parse_openapi(
        {
            "openapi": "3.0.0",
            "paths": {
                "/users": {
                    "get": {"summary": "List users"},
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UserCreate"}
                                }
                            }
                        }
                    },
                }
            },
            "components": {"schemas": {"UserCreate": {"type": "object"}}},
        }
    )
    assert any(item.entity_type == "endpoint" and item.name == "GET /users" for item in entities)
    assert any(item.entity_type == "schema" and item.name == "UserCreate" for item in entities)
    assert any(
        item.relationship_type == "uses" and item.target == "UserCreate"
        for item in relationships
    )


def test_extract_schema_intelligence_routes_by_extension():
    entities, _relationships = extract_schema_intelligence("CREATE TABLE t (id INT);", ".sql")
    assert any(item.entity_type == "table" for item in entities)

    drizzle_entities, _ = extract_schema_intelligence(
        "export const users = pgTable('users', { id: uuid('id').primaryKey() })",
        ".ts",
    )
    assert any(item.entity_type == "table" and item.name == "users" for item in drizzle_entities)
