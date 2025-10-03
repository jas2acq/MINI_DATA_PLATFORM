"""Utility functions for logging and Vault client initialization.

This module provides centralized logging configuration and Vault client setup
for the Mini Data Platform ETL pipeline.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

import hvac


def setup_logger(
    logger_name: str,
    log_file_path: str,
    level: int = logging.INFO,
    max_bytes: int = 10485760,
    backup_count: int = 5,
) -> logging.Logger:
    """Configure and return a logger with file and console handlers.

    Creates a logger with both file and console output. File handler uses
    rotation to manage log file size. Log directory is created if it doesn't exist.

    Args:
        logger_name: Name of the logger (e.g., 'ingestion', 'validation').
        log_file_path: Absolute path to the log file.
        level: Logging level (default: logging.INFO).
        max_bytes: Maximum size of log file before rotation (default: 10MB).
        backup_count: Number of backup files to keep (default: 5).

    Returns:
        Configured logging.Logger instance.

    Raises:
        OSError: If log directory cannot be created.
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file_path)
    os.makedirs(log_dir, exist_ok=True)

    # Create logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Prevent adding duplicate handlers
    if logger.handlers:
        return logger

    # Create formatters
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file_path,
        mode="a",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_vault_client(
    vault_url: str | None = None,
    vault_token: str | None = None,
) -> hvac.Client:
    """Initialize and return an authenticated HashiCorp Vault client.

    Retrieves Vault connection details from environment variables if not provided.
    Authenticates using a token and verifies the connection.

    Args:
        vault_url: Vault server URL (default: from VAULT_ADDR env variable).
        vault_token: Vault authentication token (default: from VAULT_TOKEN env variable).

    Returns:
        Authenticated hvac.Client instance.

    Raises:
        ValueError: If required environment variables are missing.
        hvac.exceptions.VaultError: If authentication fails.
        ConnectionError: If cannot connect to Vault server.
    """
    # Get Vault URL from environment if not provided
    # Note: Default uses HTTP for local development only.
    # For production, set VAULT_ADDR environment variable with HTTPS URL.
    if vault_url is None:
        vault_url = os.getenv("VAULT_ADDR", "http://vault:8200")  # nosem: python.lang.security.audit.non-https-connection.non-https-connection

    # Get Vault token from environment if not provided
    if vault_token is None:
        vault_token = os.getenv("VAULT_DEV_ROOT_TOKEN_ID")
        if not vault_token:
            raise ValueError(
                "Vault token not provided and VAULT_DEV_ROOT_TOKEN_ID not set in environment"
            )

    try:
        # Initialize Vault client
        client = hvac.Client(url=vault_url, token=vault_token)

        # Verify authentication
        if not client.is_authenticated():
            raise hvac.exceptions.VaultError("Failed to authenticate with Vault")

        return client

    except hvac.exceptions.VaultError as e:
        raise hvac.exceptions.VaultError(f"Vault authentication error: {str(e)}") from e
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Vault at {vault_url}: {str(e)}") from e
