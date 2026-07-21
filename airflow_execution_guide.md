# Airflow Orchestration: Execution Handoff Guide

## Overview
This document contains the exact specifications for the Docker engineer to spin up Apache Airflow, and the Python DAG required to orchestrate the NIFTY IT pipeline (`ingest.py` -> `transform.py`).

## 1. Docker Setup (For the DevOps Engineer)

To run the pipeline tasks inside Airflow, the Airflow worker nodes need our specific Python packages (`yfinance`, `sqlalchemy`, etc.). We cannot use the raw `apache/airflow` image out-of-the-box. We must build a custom image.

### Extending the Airflow Image
Create a `requirements.txt` in the root of the project:
```text
yfinance
pandas
sqlalchemy
psycopg2-binary
python-dotenv
```

Create a `Dockerfile` in the root:
```dockerfile
FROM apache/airflow:2.8.1
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt
```

When downloading the official Airflow `docker-compose.yaml`, modify the `x-airflow-common` block to build from the Dockerfile rather than pulling the raw image:
```yaml
x-airflow-common:
  &airflow-common
  # image: ${AIRFLOW_IMAGE_NAME:-apache/airflow:2.8.1}  <-- Comment this out
  build: .                                              # <-- Add this
```

### Directory Structure Mapping
Ensure the docker-compose file mounts the Python scripts so the DAG can execute them.
```yaml
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
      - ./plugins:/opt/airflow/plugins
      - ./:/opt/airflow/scripts  # <-- Mount the root folder here
```

---

## 2. The DAG File (For the Pipeline Engineer)

Save the following code inside the `dags/` folder as `equity_pipeline_dag.py`. Airflow will automatically detect it and parse the workflow.

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

# Define default arguments
default_args = {
    'owner': 'abhinav',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG
with DAG(
    'nifty_it_equity_pipeline',
    default_args=default_args,
    description='Automated ETL pipeline for NIFTY IT stock data',
    schedule_interval='0 23 * * 1-5', # Run at 11:00 PM, Monday through Friday
    catchup=False,
    tags=['finance', 'equity', 'etl'],
) as dag:

    # Task 1: Ingestion Layer (Extract & Load)
    ingest_task = BashOperator(
        task_id='run_ingestion',
        bash_command='python /opt/airflow/scripts/ingest.py',
    )

    # Task 2: Transformation Layer (Business Logic & Upserts)
    transform_task = BashOperator(
        task_id='run_transformation',
        bash_command='python /opt/airflow/scripts/transform.py',
    )

    # Define Dependencies: Transform will only run if Ingest succeeds
    ingest_task >> transform_task
```

---

## 3. Database Networking (Crucial Step)

Because the Python scripts will now execute *inside* a Docker container, they can no longer use `localhost` to connect to the PostgreSQL database running natively on the Windows host machine. 

The `.env` file mounted into the Airflow container must be updated to use Docker's internal host mapping:

```text
DB_USER=postgres
DB_PASSWORD=your_actual_password
DB_HOST=host.docker.internal     # <-- CRITICAL: Do not use localhost
DB_PORT=5432
DB_NAME=equity_db
```
