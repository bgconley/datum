from datum.services.search import ParsedQuery, RankedCandidate, fuse_results, parse_query


class TestParseQuery:
    def test_basic_query(self):
        parsed = parse_query("JWT token lifetime")
        assert isinstance(parsed, ParsedQuery)
        assert parsed.bm25_query == "JWT token lifetime"

    def test_detects_version_numbers(self):
        parsed = parse_query("upgrade to v3.0.0")
        assert any(term.term_type == "version" for term in parsed.detected_terms)

    def test_detects_env_vars(self):
        parsed = parse_query("set DATABASE_URL to postgres")
        assert any(term.term_type == "env_var" for term in parsed.detected_terms)

    def test_detects_api_routes(self):
        parsed = parse_query("GET /api/v1/users endpoint")
        assert any(term.term_type == "api_route" for term in parsed.detected_terms)


class TestFuseResults:
    def test_rrf_combines_signals(self):
        bm25 = [RankedCandidate(chunk_id="a", rank=1), RankedCandidate(chunk_id="b", rank=2)]
        vector = [RankedCandidate(chunk_id="b", rank=1), RankedCandidate(chunk_id="c", rank=2)]
        fused = fuse_results(bm25_results=bm25, vector_results=vector)
        assert fused[0].chunk_id == "b"

    def test_rrf_handles_empty(self):
        assert fuse_results(bm25_results=[], vector_results=[]) == []

    def test_rrf_deduplicates(self):
        bm25 = [RankedCandidate(chunk_id="a", rank=1)]
        vector = [RankedCandidate(chunk_id="a", rank=1)]
        fused = fuse_results(bm25_results=bm25, vector_results=vector)
        assert len(fused) == 1
