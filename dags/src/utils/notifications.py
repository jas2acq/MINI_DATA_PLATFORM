"""Email notification functions for Airflow DAG callbacks.

This module provides functions to send email notifications for
DAG task success and failure events.
"""

import logging
from typing import Any

from airflow.utils.email import send_email

logger = logging.getLogger(__name__)


def send_success_notification(context: dict[str, Any]) -> None:
    """Send email notification on DAG task success.

    This function is designed to be used as an Airflow `on_success_callback`.

    Args:
        context: Airflow context dictionary containing task execution metadata.

    Raises:
        Exception: If email sending fails (logged but not raised to avoid task failure).
    """
    dag = context.get("dag")
    dag_id = dag.dag_id if dag else "Unknown DAG"

    task_instance = context.get("task_instance")
    task_id = task_instance.task_id if task_instance else "Unknown Task"

    execution_date_obj = context.get("execution_date")
    execution_date = execution_date_obj.isoformat() if execution_date_obj else "Unknown Date"

    subject = f"Success: {dag_id} - {task_id}"
    html_content = f"""
    <html>
      <body>
        <h2>Task Execution Successful</h2>
        <ul>
          <li><strong>DAG:</strong> {dag_id}</li>
          <li><strong>Task:</strong> {task_id}</li>
          <li><strong>Execution Date:</strong> {execution_date}</li>
          <li><strong>Status:</strong> <span style="color: green;">SUCCESS</span></li>
        </ul>
        <p>The task completed successfully without errors.</p>
      </body>
    </html>
    """

    try:
        # Send email using Airflow's configured SMTP connection
        send_email(
            to=["admin@example.com"],  # Configure via Airflow Variables or env
            subject=subject,
            html_content=html_content,
        )
        logger.info(f"Success notification sent for {dag_id}.{task_id}")
    except Exception as e:
        logger.error(f"Failed to send success notification: {str(e)}")
        # Don't raise exception to avoid marking successful task as failed


def send_failure_notification(context: dict[str, Any]) -> None:
    """Send email notification on DAG task failure.

    This function is designed to be used as an Airflow `on_failure_callback`.

    Args:
        context: Airflow context dictionary containing task execution metadata.

    Raises:
        Exception: If email sending fails (logged but not raised to avoid complicating failure).
    """
    dag = context.get("dag")
    dag_id = dag.dag_id if dag else "Unknown DAG"

    task_instance = context.get("task_instance")
    task_id = task_instance.task_id if task_instance else "Unknown Task"

    execution_date_obj = context.get("execution_date")
    execution_date = execution_date_obj.isoformat() if execution_date_obj else "Unknown Date"
    exception = context.get("exception", "No exception details available")
    log_url = task_instance.log_url if task_instance else "#"

    subject = f"Failure: {dag_id} - {task_id}"
    html_content = f"""
    <html>
      <body>
        <h2>Task Execution Failed</h2>
        <ul>
          <li><strong>DAG:</strong> {dag_id}</li>
          <li><strong>Task:</strong> {task_id}</li>
          <li><strong>Execution Date:</strong> {execution_date}</li>
          <li><strong>Status:</strong> <span style="color: red;">FAILURE</span></li>
        </ul>
        <h3>Exception Details:</h3>
        <pre>{exception}</pre>
        <p><a href="{log_url}">View Task Logs</a></p>
      </body>
    </html>
    """

    try:
        # Send email using Airflow's configured SMTP connection
        send_email(
            to=["admin@example.com"],  # Configure via Airflow Variables or env
            subject=subject,
            html_content=html_content,
        )
        logger.info(f"Failure notification sent for {dag_id}.{task_id}")
    except Exception as e:
        logger.error(f"Failed to send failure notification: {str(e)}")
        # Don't raise exception to avoid complicating the original failure
