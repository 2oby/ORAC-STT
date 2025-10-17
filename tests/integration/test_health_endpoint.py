"""Integration tests for health endpoint."""

import pytest


def test_health_endpoint_returns_200(test_client):
    """Test that health endpoint returns 200 status."""
    response = test_client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_returns_json(test_client):
    """Test that health endpoint returns valid JSON."""
    response = test_client.get("/health")
    data = response.json()
    assert isinstance(data, dict)


def test_health_endpoint_has_status_field(test_client):
    """Test that health endpoint includes status field."""
    response = test_client.get("/health")
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "initializing", "unhealthy"]


def test_health_endpoint_has_timestamp(test_client):
    """Test that health endpoint includes timestamp."""
    response = test_client.get("/health")
    data = response.json()
    assert "timestamp" in data
