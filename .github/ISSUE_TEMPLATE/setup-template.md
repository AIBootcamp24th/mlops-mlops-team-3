---
name: "Project Setup & Infrastructure"
about: "프로젝트 초기 환경 구축 및 인프라 설계를 위한 템플릿"
title: "[Setup] "
labels: ["chore", "infrastructure"]
assignees: ""
---

## Description
팀 프로젝트의 재현성을 보장하기 위해 `uv`를 활용한 표준 개발 환경을 구축하고, 모델 실험 기록을 위한 W&B 인프라를 연동.

## Checklist
- [ ] **uv 기반 패키지 매니지먼트**: `pyproject.toml` 및 `uv.lock` 설정을 통한 팀원 간 동일 환경 보장 (Python 3.11)
- [ ] **MLOps 인프라 세팅**: W&B Team Entity(`mlops-team3`) 연동 및 베이스라인 테스트 코드 작성 (`main.py`)
- [ ] **프로젝트 구조 표준화**: `data/`, `src/`, `models/`, `notebooks/` 등 표준 폴더 구조 제안 및 생성
- [ ] **TMDB 데이터 피처 리서치**: 평점(`vote_average`) 예측에 유의미한 변수(장르, 예산, 줄거리 등) 선별
- [ ] 하이브리드 Cloud 인프라 구상:
    - Management: AWS EC2 `t3.small` (경량 서버/API/CI/CD 거점)
    - Training: 필요 시 GPU 인스턴스(G4dn 등) Spot 활용 전략 수립
     
## Note
- `git pull` 후 `uv sync`를 실행하면 즉시 동일한 환경에서 작업이 가능.
- W&B 기록을 위해 각자 `uv run wandb login`을 먼저 진행.

## Hardware Spec
--------------------------------------------------------------------------------
- Instance Type: t3.small
- vCPU: 2 / Memory: 2 GiB
- Storage: 30GB EBS (GP3)
- OS: Ubuntu 24.04 LTS
