from fastapi.testclient import TestClient


def test_responses_carry_owasp_security_headers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in response.headers
    assert (
        response.headers["Content-Security-Policy"]
        == "default-src 'none'; frame-ancestors 'none'"
    )


def test_hsts_is_absent_outside_production(client: TestClient) -> None:
    # Test settings run with ENVIRONMENT=test -- HSTS must not be sent, or a
    # browser would cache it and start refusing http:// to this host.
    response = client.get("/health")
    assert "Strict-Transport-Security" not in response.headers
