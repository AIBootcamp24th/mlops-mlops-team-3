# MLOps 운영 Runbook

## 1) 실행 환경 결정

- 학습 워커 기본 운영: Docker 기반 워커(`trainer-worker`)
- 단기 운영: 단일 워커 수동/스케줄 실행 + GitHub Actions 디스패치
- 확장 운영: ECS Fargate 이전을 목표로 하되, 현재는 Docker 경로를 운영 기준으로 확정

## 2) 정상 운영 절차

1. 학습 메시지 전송 자동화
   - GitHub Actions `train-dispatch.yml` 수동 또는 스케줄 실행
   - 로컬 수동 전송(필요 시): `PYTHONPATH=. uv run python scripts/send_sqs_message.py`
2. 워커 실행(로컬/원격 수동 운영)
   - `docker compose run --rm trainer-worker`
3. 학습 결과 확인
   - W&B run 상태(`finished`)
   - S3 모델 업로드(`models/{run_id}/rating_model.pt`)
   - 학습 메타데이터 업로드(`models/{run_id}/training_metadata.json`)
4. 배치 추론 배포 자동화
   - GitHub Actions `batch-infer.yml` 수동 또는 스케줄 실행
   - 워크플로우가 W&B에서 추론 모델 선택 후 S3 예측 결과 생성
5. 배치 추론 결과 확인
   - S3 예측 파일 업로드(`predictions/.../predictions.csv`)
   - Slack 성공 알림에서 모델 키/출력 키/출력 URI 확인

## 3) 장애 대응

### A. SQS 메시지 전송 실패

- 확인:
  - `TRAIN_QUEUE_URL` 값
  - IAM 권한(`sqs:SendMessage`)
- 조치:
  - AWS 자격증명 재적용 후 재전송

### B. 학습 중 S3 404

- 원인: 학습 CSV 키 미존재
- 조치:
  - 입력 데이터 업로드 후 재실행
  - 예: `tmdb/latest/train.csv`

### C. W&B 업로드 실패(엔티티 오류)

- 원인: `WANDB_ENTITY` 불일치
- 조치:
  - `.env`/Secrets에서 `WANDB_ENTITY=mlops-team3`로 수정
  - 연결 테스트 런 재실행

### D. 배치 추론 입력 스키마 오류

- 원인: 입력 CSV에 필수 feature 컬럼 누락
- 확인:
  - 기본 필수 컬럼: `budget`, `runtime`, `popularity`, `vote_count`
  - `batch-infer.yml`의 `input_s3_key`가 올바른 데이터 키인지 확인
- 조치:
  - 누락 컬럼을 포함한 CSV 재업로드 후 `batch-infer.yml` 재실행
  - 필요 시 `--feature-cols`를 데이터 스키마에 맞게 조정

### E. 모델 선택 실패(register_model)

- 원인: W&B finished run에 `model_uri` 또는 `val_rmse`가 없음
- 확인:
  - W&B run summary에 `model_uri`, `val_rmse`, `feature_cols` 기록 여부
  - 최근 학습 워커 로그에서 summary 기록 단계 오류 여부
- 조치:
  - 학습 워커 재실행 후 summary 키 기록 확인
  - 결측 run 정리 또는 신규 정상 run 생성 후 재시도

### F. Slack 알림 실패

- 확인:
  - `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`
  - `chat.postMessage` API 응답 `ok=true`
- 조치:
  - 토큰 권한(scope) 재확인 후 알림 워크플로우 재실행

## 4) 롤백 절차

- 코드/워크플로우 변경 시 이전 안정 커밋으로 복귀
- 인프라는 Terraform 기준으로 관리하고, 수동 변경은 기록 후 정리
- 장애 구간의 학습 메시지는 DLQ 유입 여부를 확인 후 재처리
- 배치 추론 장애 시 직전 정상 `output_s3_key`를 기준 결과로 임시 고정

## 5) 점검 체크리스트

- [ ] SQS `train-queue`/`train-queue-dlq` 상태 정상
- [ ] Docker 워커 실행 성공
- [ ] W&B run/metric/artifact 기록 확인
- [ ] S3 모델/메타데이터 업로드 확인 (`rating_model.pt`, `training_metadata.json`)
- [ ] `batch-infer.yml` 실행 성공 및 예측 결과 생성 확인
- [ ] 입력 CSV 최신성(freshness) 확인
- [ ] Slack 성공/실패 알림에서 workflow/run 링크 확인
