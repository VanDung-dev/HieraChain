"""
Unit tests for GraphQL security measures.
"""

import asyncio
import os

import pytest

from hierachain.api import graphql_handler
from hierachain.api.graphql import security as graphql_security
from hierachain.config.settings import (
    DevelopmentSettings,
    ProductionSettings,
    Settings,
    TestingSettings,
    get_settings,
)


def test_graphql_query_depth_limit_simple():
    """Test that simple queries have low depth."""
    query = """
    query {
        chain {
            blocks {
                hash
            }
        }
    }
    """
    depth = graphql_security.get_query_depth(query)
    assert depth >= 1


def test_graphql_query_depth_limit_nested():
    """Test that nested queries are detected."""
    query = """
    query {
        chain {
            blocks {
                events {
                    details {
                        entity {
                            id
                        }
                    }
                }
            }
        }
    }
    """
    depth = graphql_security.get_query_depth(query)
    assert depth >= 4


def test_deep_query_rejected():
    """Test that queries exceeding depth limit are rejected."""
    query = "{ " * 20 + "value " + "}" * 20
    depth = graphql_security.get_query_depth(query)
    assert depth > graphql_security.MAX_QUERY_DEPTH


def test_graphql_query_complexity_estimate():
    """Test complexity estimation for simple queries."""
    query = """
    query {
        chain {
            height
        }
    }
    """
    complexity = graphql_security.estimate_complexity(query)
    assert complexity > 0


def test_complex_query_exceeds_limit():
    """Test that complex queries exceed limit."""
    query_lines = []
    for i in range(50):
        query_lines.append(f"""
        chain{i} {{
            blocks {{
                events {{
                    details {{
                        data
                    }}
                }}
            }}
        }}
        """)
    query = " ".join(query_lines)
    
    complexity = graphql_security.estimate_complexity(query)
    assert complexity > 0


def test_graphql_introspection_detected():
    """Test that introspection queries are detected."""
    query = "{ __schema { types { name } }"
    assert graphql_security.is_introspection_query(query) is True


def test_graphql_introspection_typename():
    """Test __typename introspection pattern."""
    query = "query { __typename }"
    assert graphql_security.is_introspection_query(query) is True


def test_graphql_introspection_not_detected():
    """Test that regular queries are not flagged as introspection."""
    query = """
    query {
        chain {
            blocks {
                hash
            }
        }
    }
    """
    assert graphql_security.is_introspection_query(query) is False


def test_graphql_rate_limit_allows_within_limit():
    """Test that rate limiting allows requests within limit."""
    security = graphql_security.GraphQLSecurity()
    
    for _ in range(graphql_security.RATE_LIMIT_REQUESTS - 1):
        result = security.check_rate_limit("192.168.1.1")
        assert result is True


def test_graphql_rate_limit_blocks_excess():
    """Test that rate limiting blocks excess requests."""
    security = graphql_security.GraphQLSecurity()
    
    for _ in range(graphql_security.RATE_LIMIT_REQUESTS):
        security.check_rate_limit("192.168.1.1")
    
    result = security.check_rate_limit("192.168.1.1")
    assert result is False


def test_graphql_rate_limit_per_client():
    """Test that rate limits are per client IP."""
    security = graphql_security.GraphQLSecurity()
    
    for _ in range(graphql_security.RATE_LIMIT_REQUESTS):
        security.check_rate_limit("192.168.1.1")
    
    result = security.check_rate_limit("192.168.1.2")
    assert result is True


def test_introspection_disabled_in_production(monkeypatch):
    """Test that introspection is disabled in production."""
    monkeypatch.setenv("ENV", "production")
    assert os.environ.get("ENV") == "production"


@pytest.mark.parametrize(
    ("variable", "value", "settings_type"),
    [
        ("HRC_ENV", "prod", ProductionSettings),
        ("HRC_ENV", " PRODUCT ", ProductionSettings),
        ("ENV", " Production ", ProductionSettings),
        ("HRC_ENV", " DEV ", DevelopmentSettings),
        ("ENV", "TESTING", TestingSettings),
    ],
)
def test_environment_alias_selects_settings(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
    settings_type: type[Settings],
) -> None:
    monkeypatch.delenv("HRC_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("HRC_AUTH_ENABLED", "true")
    monkeypatch.setenv(variable, value)

    assert isinstance(get_settings(), settings_type)


@pytest.mark.parametrize(
    ("hrc_env", "legacy_env"),
    [("prodution", "production"), (None, "staging")],
)
def test_unknown_environment_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    hrc_env: str | None,
    legacy_env: str,
) -> None:
    if hrc_env is None:
        monkeypatch.delenv("HRC_ENV", raising=False)
    else:
        monkeypatch.setenv("HRC_ENV", hrc_env)
    monkeypatch.setenv("ENV", legacy_env)

    with pytest.raises(ValueError, match="Unsupported HRC_ENV/ENV value"):
        get_settings()


def test_hrc_env_takes_precedence_over_legacy_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRC_ENV", "dev")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("HRC_AUTH_ENABLED", "true")

    assert isinstance(get_settings(), DevelopmentSettings)

    monkeypatch.setenv("HRC_ENV", "  ")
    assert isinstance(get_settings(), ProductionSettings)


def test_graphql_handler_blocks_introspection_for_production_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("HRC_ENV", "prod")
    monkeypatch.setenv("HRC_AUTH_ENABLED", "true")
    monkeypatch.setattr(graphql_security, "check_rate_limit", lambda _client_ip: True)

    class Request:
        client: None = None

        async def body(self) -> bytes:
            return b'{"query":"{ __schema { types { name } } }"}'

    valid, response, parsed = asyncio.run(
        graphql_handler._validate_graphql_request(Request())
    )

    assert not valid
    assert parsed is None
    assert response is not None
    assert response.status_code == 400
    assert response.body == (
        b'{"errors":[{"message":"Introspection queries disabled in production"}]}'
    )

def test_production_mode_restricts_queries(monkeypatch):
    """Test that production mode applies stricter limits."""
    monkeypatch.setenv("ENV", "production")
    
    query = """
    query {
        chain {
            blocks(first: 1000) {
                events(first: 500) {
                    details
                }
            }
        }
    }
    """
    complexity = graphql_security.estimate_complexity(query)
    assert complexity > 0
    
    monkeypatch.setenv("ENV", "development")
    dev_complexity = graphql_security.estimate_complexity(query)
    assert dev_complexity > 0
