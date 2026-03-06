from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


with DAG(
    dag_id="mlops_train_then_infer_pipeline",
    default_args={"owner": "mlops-team3"},
    start_date=datetime(2026, 2, 27),
    end_date=datetime(2026, 3, 11, 23, 59, 59),
    schedule=None,
    catchup=False,
    tags=["mlops", "orchestration", "train", "infer"],
) as dag:
    trigger_train = TriggerDagRunOperator(
        task_id="trigger_train_pipeline",
        trigger_dag_id="mlops_train_pipeline",
        wait_for_completion=True,
        allowed_states=["success"],
        failed_states=["failed"],
        poke_interval=20,
    )

    trigger_infer = TriggerDagRunOperator(
        task_id="trigger_infer_pipeline",
        trigger_dag_id="mlops_infer_pipeline",
        wait_for_completion=True,
        allowed_states=["success"],
        failed_states=["failed"],
        poke_interval=20,
    )

    trigger_train >> trigger_infer
