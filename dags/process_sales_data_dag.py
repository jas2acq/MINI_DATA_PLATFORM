"""Airflow DAG for processing sales data from MinIO to PostgreSQL.

This DAG runs daily at 2 AM, polls MinIO for new files in the raw/ prefix,
and triggers the ETL pipeline for each file found.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor

from dags.src.pipeline import run_pipeline
from dags.src.utils.notifications import send_failure_notification, send_success_notification

# Default arguments for the DAG
default_args = {
    "owner": "data-platform-team",
    "depends_on_past": False,
    "email": ["admin@example.com"],
    "email_on_failure": False,  # Using custom notification callbacks instead
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": send_failure_notification,
    "on_success_callback": send_success_notification,
}


def process_file_from_xcom(**context) -> None:
    """Retrieve file key from XCom and trigger ETL pipeline.

    Args:
        **context: Airflow context containing XCom data.

    Raises:
        ValueError: If no file key found in XCom.
    """
    # Pull the file key from XCom (pushed by S3KeySensor)
    task_instance = context["task_instance"]
    file_key = task_instance.xcom_pull(task_ids="sense_new_file")

    if not file_key:
        raise ValueError("No file key found in XCom from sensor task")

    # Run the ETL pipeline for the file
    run_pipeline(file_key)


# Define the DAG
with DAG(
    dag_id="process_sales_data",
    default_args=default_args,
    description="ETL pipeline for sales data from MinIO to PostgreSQL",
    schedule_interval="0 2 * * *",  # Run daily at 2 AM
    start_date=datetime(2025, 10, 1),
    catchup=False,
    tags=["etl", "sales", "minio", "postgres"],
) as dag:
    # Task 1: Sense new files in MinIO raw/ prefix
    sense_new_file = S3KeySensor(
        task_id="sense_new_file",
        bucket_name="data-platform",
        bucket_key="raw/*.csv",
        wildcard_match=True,
        aws_conn_id="minio_conn",  # Configure in Airflow UI
        timeout=3600,  # 1 hour timeout
        poke_interval=300,  # Check every 5 minutes
        mode="poke",
        soft_fail=False,
        dag=dag,
    )

    # Task 2: Process the file using the ETL pipeline
    process_file = PythonOperator(
        task_id="process_file",
        python_callable=process_file_from_xcom,
        provide_context=True,
        dag=dag,
    )

    # Define task dependencies
    sense_new_file >> process_file
