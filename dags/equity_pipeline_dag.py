from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'abhinav',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'nifty_it_equity_pipeline',
    default_args=default_args,
    description='Automated ETL pipeline for NIFTY IT stock data',
    schedule_interval='0 23 * * 1-5',
    catchup=False,
    tags=['finance', 'equity', 'etl'],
) as dag:

    ingest_task = BashOperator(
        task_id='run_ingestion',
        bash_command='python /opt/airflow/scripts/ingest.py',
    )

    transform_task = BashOperator(
        task_id='run_transformation',
        bash_command='python /opt/airflow/scripts/transform.py',
    )

    ingest_task >> transform_task
