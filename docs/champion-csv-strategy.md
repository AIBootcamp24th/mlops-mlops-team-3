# Champion CSV 전략 - 호환 모드, 롤백, 검증 절차

## 개요

`tmdb/{approved_run_id}/*.csv` 규칙으로 S3 데이터를 표준화하고, RDS/Aurora `tmdb_dataset_registry`에 메타데이터를 저장합니다.

## S3 경로 규칙

| 파일 유형 | 경로 형식 | 버킷 |
|----------|-----------|------|
| train.csv | `tmdb/{approved_run_id}/train.csv` | AWS_S3_RAW_BUCKET |
| infer.csv | `tmdb/{approved_run_id}/infer.csv` | AWS_S3_RAW_BUCKET |
| predictions | `tmdb/{approved_run_id}/predictions_{ds}_{ts}.csv` | AWS_S3_PRED_BUCKET |

## 호환 모드

### 1단계 (현재)

- **train**: `tmdb/{ts_nodash}/train.csv`로 export 후 SQS dispatch. `register_model` 완료 시 `tmdb/{approved_run_id}/train.csv`로 복사.
- **infer**: champion registry 필수. `approved_run_id` 없으면 추론 파이프라인 실패.
- **predictions**: champion prefix 사용. 기존 `pred/batch/*` 경로는 사용하지 않음.

### 2단계 (향후)

- train export를 champion prefix로 직접 저장하는 방식 검토 (선행 champion이 있을 경우 fallback).
- `tmdb/latest/infer.csv` 호환 경로 제거.

### 3단계 (정리)

- `tmdb/{ts}/train.csv` 중간 경로 제거.
- 문서/운영 체크리스트 최종 정리.

## 롤백 기준

다음 경우 롤백을 고려합니다.

1. **champion.json 없음**: 품질 게이트 미실행 시 infer 파이프라인 실패.
2. **RDS/Aurora 연결 실패**: `tmdb_dataset_registry` upsert 실패 시 해당 단계만 스킵 (파이프라인은 계속 진행).
3. **S3 복사 실패**: `register_model`의 train 복사 실패 시 경고만 출력, champion.json은 정상 기록.

### 롤백 절차

1. **환경변수로 fallback**: `API_MODEL_S3_KEY`를 직접 지정하면 champion registry 조회를 우회.
2. **infer 입력 fallback**: `INFER_DATA_S3_KEY`를 `tmdb/latest/infer.csv` 등으로 지정하면 `export_infer_to_s3`에서 해당 경로 사용 (단, `approved_run_id`가 경로에서 추출 가능해야 함).
3. **DAG 스킵**: `export_infer_to_s3` 태스크를 수동으로 skip하고, 기존 `tmdb/latest/infer.csv`가 있다면 `send_infer_sqs_message`를 수정해 임시로 고정 경로 사용.

## 검증 절차

### 1. champion 레지스트리 유효성

```bash
# champion.json 존재 및 필수 필드 확인
aws s3 cp s3://{AWS_S3_MODEL_BUCKET}/models/registry/champion.json - | jq '.approved_run_id, .model_key'
```

### 2. S3 객체 존재 확인

```bash
# champion prefix 내 CSV 확인
aws s3 ls s3://{AWS_S3_RAW_BUCKET}/tmdb/{approved_run_id}/
aws s3 ls s3://{AWS_S3_PRED_BUCKET}/tmdb/{approved_run_id}/
```

### 3. RDS/Aurora 레코드와 S3 교차 검증

```sql
SELECT approved_run_id, csv_type, s3_key, row_count, created_at
FROM tmdb_dataset_registry
ORDER BY created_at DESC
LIMIT 20;
```

### 4. 테스트 실행

```bash
uv run pytest tests/test_sqs_payload_integration.py tests/test_registry_schema.py -v
```

### 5. DAG 파싱 검증

```bash
# Airflow 로컬 실행 시
astro dev parse
# 또는
python -c "from airflow.dags.mlops_infer_pipeline import dag; print('OK')"
```

## 운영 체크리스트

- [ ] `tmdb_dataset_registry` 테이블이 RDS/Aurora에 생성됨
- [ ] champion.json에 `approved_run_id`, `model_key` 존재
- [ ] train 파이프라인 완료 후 `tmdb/{approved_run_id}/train.csv` 존재
- [ ] infer 파이프라인 완료 후 `tmdb/{approved_run_id}/infer.csv`, `predictions_*.csv` 존재
- [ ] `tmdb_dataset_registry`에 train/infer/predictions 레코드가 기록됨
- [ ] champion 모델 로딩/핫리로드 동작에 회귀 없음
