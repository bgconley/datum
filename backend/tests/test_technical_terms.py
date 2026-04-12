from datum.services.technical_terms import TermMatch, extract_technical_terms


class TestExtractTechnicalTerms:
    def test_api_routes(self):
        text = "The endpoint GET /api/v2/users returns a list. Also POST /api/v1/auth/login."

        terms = extract_technical_terms(text)
        routes = [term for term in terms if term.term_type == "api_route"]

        assert len(routes) == 2
        assert all(isinstance(term, TermMatch) for term in routes)
        assert any("/api/v2/users" in term.raw_text for term in routes)

    def test_file_paths(self):
        text = "Config is at /etc/nginx/nginx.conf and logs at /var/log/app.log."

        terms = extract_technical_terms(text)
        paths = [term for term in terms if term.term_type == "file_path"]

        assert len(paths) == 2

    def test_sql_identifiers(self):
        text = "Query: SELECT * FROM users WHERE users.role = 'admin';"

        terms = extract_technical_terms(text)
        identifiers = [term for term in terms if term.term_type == "sql_identifier"]

        assert any("users" in term.normalized_text for term in identifiers)

    def test_env_vars(self):
        text = "Set DATABASE_URL and REDIS_HOST before starting."

        terms = extract_technical_terms(text)
        env_vars = [term for term in terms if term.term_type == "env_var"]

        assert len(env_vars) == 2

    def test_version_numbers(self):
        text = "Upgraded from v2.3.1 to v3.0.0-beta.1. Also uses Python 3.12."

        terms = extract_technical_terms(text)
        versions = [term for term in terms if term.term_type == "version"]

        assert len(versions) >= 2

    def test_package_names(self):
        text = "Install with pip install fastapi uvicorn[standard] sqlalchemy."

        terms = extract_technical_terms(text)
        packages = [term for term in terms if term.term_type == "package"]

        assert any("fastapi" in term.normalized_text for term in packages)
        assert any("sqlalchemy" in term.normalized_text for term in packages)

    def test_preserves_offsets(self):
        text = "Use DATABASE_URL here."

        terms = extract_technical_terms(text)

        for term in terms:
            assert text[term.start_char:term.end_char] == term.raw_text

    def test_empty_text(self):
        assert extract_technical_terms("") == []
