"""Unit tests for utility helper functions."""

import os
from unittest.mock import patch

import hvac
import pytest

from dags.src.utils.helpers import get_vault_client, setup_logger


def test_setup_logger_creates_logger():
    """Test that logger is created with correct configuration."""
    logger = setup_logger("test_logger", "logs/test.log")

    assert logger.name == "test_logger"
    assert len(logger.handlers) == 2  # File and console handlers


def test_get_vault_client_with_valid_token(mock_vault_client):
    """Test Vault client initialization with valid credentials."""
    with patch("dags.src.utils.helpers.hvac.Client", return_value=mock_vault_client):
        with patch.dict(os.environ, {"VAULT_DEV_ROOT_TOKEN_ID": "test_token"}):
            client = get_vault_client()

            assert client is not None
            client.is_authenticated.assert_called_once()


def test_get_vault_client_without_token():
    """Test that Vault client raises error without token."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Vault token not provided"):
            get_vault_client()


def test_get_vault_client_authentication_failure(mock_vault_client):
    """Test Vault client handles authentication failure."""
    mock_vault_client.is_authenticated.return_value = False

    with patch("dags.src.utils.helpers.hvac.Client", return_value=mock_vault_client):
        with patch.dict(os.environ, {"VAULT_DEV_ROOT_TOKEN_ID": "invalid"}):
            with pytest.raises(hvac.exceptions.VaultError, match="Failed to authenticate"):
                get_vault_client()
