# 롤아웃 가드레일 및 E2E 검증

## 개요

배포 전 스테이징 환경에서 핵심 경로를 검증하고, 점진 롤아웃 시 리스크를 관리하기 위한 가이드입니다.

## 단계별 검증 체크리스트

### 1단계 배포 전 (운영 리스크 완화)

- [ ] `predictor.check_and_reload`가 `approved_run_id`, `model_key`로 champion.json 파싱
- [ ] 추론 워커 빈 큐 시 예외 종료 없이 sleep 후 재폴링
- [ ] `APP_ENV=production`에서 DB 크리덴셜 미설정 시 즉시 실패
- [ ] CORS 기본값이 화이트리스트 (`*` 아님)
- [ ] Airflow 초기 계정이 `AIRFLOW_ADMIN_*` 환경변수로 주입

### 2단계 배포 전 (데이터/학습 품질)

- [ ] `check_data_change`가 count + fingerprint 복합 비교
- [ ] 학습 데이터 `min_train_samples` 미달 시 실패 처리 (복제 학습 없음)
- [ ] `early_stopping_patience` 기반 조기 종료 동작

### 3단계 배포 전 (오케스트레이션/검증)

- [ ] 학습 DAG: DAG 내부 동기 실행 모드 명시
- [ ] 추론 DAG: `verify_infer_result` 태스크로 결과 파일 검증
- [ ] 통합 테스트: registry 스키마, SQS payload, quality gate 분기

## E2E 검증 실행

```bash
# 스테이징에서 1회 실행 (필수 환경변수 설정 후)
./scripts/verify_staging_e2e.sh
```

## 환경변수 기반 토글

| 변수 | 용도 | 기본값 |
|------|------|--------|
| `QUALITY_GATE_REQUIRED` | 품질 게이트 차단 여부 | `true` |
| `APP_ENV` | 운영 시 크리덴셜 fail-fast | `development` |
| `MIN_TRAIN_SAMPLES` | 최소 학습 건수 (payload) | `50` |
| `EARLY_STOPPING_PATIENCE` | 조기 종료 patience (payload) | `10` |

## 롤아웃 리스크 관리

- 레지스트리 스키마: `approved_run_id`/`model_key` 우선, `run_id`/`s3_key` 하위호환 유지
- 각 단계 배포 후 스테이징에서 SQS → 학습 → 등록 → 추론 E2E 1회 검증 권장
