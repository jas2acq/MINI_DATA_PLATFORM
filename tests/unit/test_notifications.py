"""Unit tests for email notification functions."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from dags.src.utils.notifications import (
    send_failure_notification,
    send_success_notification,
)


@pytest.fixture
def mock_success_context():
    """Create mock Airflow context for successful task."""
    dag = MagicMock()
    dag.dag_id = "test_dag"

    task_instance = MagicMock()
    task_instance.task_id = "test_task"

    return {
        "dag": dag,
        "task_instance": task_instance,
        "execution_date": datetime(2025, 10, 1, 12, 0, 0),
    }


@pytest.fixture
def mock_failure_context():
    """Create mock Airflow context for failed task."""
    dag = MagicMock()
    dag.dag_id = "test_dag"

    task_instance = MagicMock()
    task_instance.task_id = "test_task"
    task_instance.log_url = "http://localhost:8080/log"

    return {
        "dag": dag,
        "task_instance": task_instance,
        "execution_date": datetime(2025, 10, 1, 12, 0, 0),
        "exception": "ValueError: Test error",
    }


def test_send_success_notification_success(mock_success_context):
    """Test successful sending of success notification."""
    with patch("dags.src.utils.notifications.send_email") as mock_send:
        send_success_notification(mock_success_context)

        mock_send.assert_called_once()
        args = mock_send.call_args
        assert args[1]["subject"] == "Success: test_dag - test_task"
        assert "SUCCESS" in args[1]["html_content"]
        assert "test_dag" in args[1]["html_content"]
        assert "test_task" in args[1]["html_content"]


def test_send_success_notification_with_missing_context_fields():
    """Test success notification with missing context fields."""
    context = {}

    with patch("dags.src.utils.notifications.send_email") as mock_send:
        send_success_notification(context)

        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "Unknown DAG" in args[1]["subject"]
        assert "Unknown Task" in args[1]["subject"]
        assert "Unknown Date" in args[1]["html_content"]


def test_send_success_notification_email_error(mock_success_context):
    """Test success notification when email sending fails."""
    with patch("dags.src.utils.notifications.send_email") as mock_send:
        mock_send.side_effect = Exception("SMTP error")

        # Should not raise exception
        send_success_notification(mock_success_context)

        # Verify email was attempted
        mock_send.assert_called_once()


def test_send_failure_notification_success(mock_failure_context):
    """Test successful sending of failure notification."""
    with patch("dags.src.utils.notifications.send_email") as mock_send:
        send_failure_notification(mock_failure_context)

        mock_send.assert_called_once()
        args = mock_send.call_args
        assert args[1]["subject"] == "Failure: test_dag - test_task"
        assert "FAILURE" in args[1]["html_content"]
        assert "test_dag" in args[1]["html_content"]
        assert "test_task" in args[1]["html_content"]
        assert "ValueError: Test error" in args[1]["html_content"]
        assert "http://localhost:8080/log" in args[1]["html_content"]


def test_send_failure_notification_with_missing_context_fields():
    """Test failure notification with missing context fields."""
    context = {}

    with patch("dags.src.utils.notifications.send_email") as mock_send:
        send_failure_notification(context)

        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "Unknown DAG" in args[1]["subject"]
        assert "Unknown Task" in args[1]["subject"]
        assert "Unknown Date" in args[1]["html_content"]
        assert "No exception details available" in args[1]["html_content"]


def test_send_failure_notification_email_error(mock_failure_context):
    """Test failure notification when email sending fails."""
    with patch("dags.src.utils.notifications.send_email") as mock_send:
        mock_send.side_effect = Exception("SMTP error")

        # Should not raise exception
        send_failure_notification(mock_failure_context)

        # Verify email was attempted
        mock_send.assert_called_once()


def test_send_success_notification_content_format(mock_success_context):
    """Test that success notification has correct HTML format."""
    with patch("dags.src.utils.notifications.send_email") as mock_send:
        send_success_notification(mock_success_context)

        args = mock_send.call_args
        html_content = args[1]["html_content"]

        # Check HTML structure
        assert "<html>" in html_content
        assert "<body>" in html_content
        assert "<h2>Task Execution Successful</h2>" in html_content
        assert "<strong>DAG:</strong>" in html_content
        assert "<strong>Task:</strong>" in html_content
        assert "<strong>Execution Date:</strong>" in html_content
        assert 'color: green' in html_content


def test_send_failure_notification_content_format(mock_failure_context):
    """Test that failure notification has correct HTML format."""
    with patch("dags.src.utils.notifications.send_email") as mock_send:
        send_failure_notification(mock_failure_context)

        args = mock_send.call_args
        html_content = args[1]["html_content"]

        # Check HTML structure
        assert "<html>" in html_content
        assert "<body>" in html_content
        assert "<h2>Task Execution Failed</h2>" in html_content
        assert "<h3>Exception Details:</h3>" in html_content
        assert "<pre>" in html_content
        assert "View Task Logs" in html_content
        assert 'color: red' in html_content


def test_send_success_notification_recipient_list(mock_success_context):
    """Test that success notification is sent to correct recipients."""
    with patch("dags.src.utils.notifications.send_email") as mock_send:
        send_success_notification(mock_success_context)

        args = mock_send.call_args
        assert args[1]["to"] == ["admin@example.com"]


def test_send_failure_notification_recipient_list(mock_failure_context):
    """Test that failure notification is sent to correct recipients."""
    with patch("dags.src.utils.notifications.send_email") as mock_send:
        send_failure_notification(mock_failure_context)

        args = mock_send.call_args
        assert args[1]["to"] == ["admin@example.com"]
