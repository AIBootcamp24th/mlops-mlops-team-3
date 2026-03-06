# TMDB ID 기반 분석 API 가이드

## 1) 한 문장 요약

`/analyze/id`는 TMDB 영화 ID를 직접 입력받아, 기존 `/analyze`와 동일한 형식의 평점 예측 + 추천 결과를 반환하는 API입니다.

## 2) 쉬운 설명 (Teach)

기존 `/analyze`는 영화 제목으로 검색합니다.  
하지만 제목은 띄어쓰기/동명이 영화 때문에 결과가 달라질 수 있습니다.

`/analyze/id`는 숫자 ID를 쓰기 때문에 기준이 더 명확합니다.

- 제목 검색 단계 없이 바로 영화 상세를 가져옵니다.
- 같은 입력 ID면 같은 기준 영화를 분석합니다.
- 응답 형식은 기존 `/analyze`와 같아서 프론트/클라이언트 변경이 작습니다.

## 3) 핵심 구성요소 역할

- `src/api/schemas.py`
  - `AnalyzeByIdRequest` 스키마로 `movie_id`, `top_k`, `user_history`를 검증합니다.
- `src/api/main.py`
  - `POST /analyze/id` 엔드포인트를 처리합니다.
  - 내부 공통 분석 함수(`_analyze_with_base_movie`)로 추천/점수 계산을 재사용합니다.
- `src/api/tmdb_client.py`
  - TMDB 상세/추천 조회를 수행합니다.
  - 세션 재사용, 재시도, TTL 캐시로 API 호출 안정성을 높입니다.

## 4) 헷갈리는 포인트 (Q/A)

Q. `/analyze`와 `/analyze/id`의 차이는 무엇인가요?  
A. 입력 기준만 다릅니다. `/analyze`는 제목, `/analyze/id`는 TMDB `movie_id`를 받습니다.

Q. 응답 구조도 다른가요?  
A. 아닙니다. 둘 다 `query_title`, `movie`, `recommendations`를 동일하게 반환합니다.

Q. 존재하지 않는 ID를 보내면 어떻게 되나요?  
A. `404`와 함께 `해당 movie_id를 찾을 수 없습니다.`를 반환합니다.

Q. TMDB 자체 장애가 나면 어떻게 되나요?  
A. 네트워크/외부 API 오류는 `502`로 처리됩니다.

## 5) 다시 단순화한 흐름

```mermaid
graph LR
  client[Client] --> api[POSTAnalyzeId]
  api --> detail[TMDBMovieDetailById]
  detail --> reco[TMDBRecommendations]
  reco --> score[PredictAndPersonalize]
  score --> response[AnalyzeResponse]
```

## 6) 요청/응답 예시

요청:

```bash
curl -X POST http://localhost:8000/analyze/id \
  -H "Content-Type: application/json" \
  -d '{
    "movie_id": 1,
    "top_k": 3,
    "user_history": [
      {"title": "살인의 추억", "rating": 9.0}
    ]
  }'
```

응답(예시):

```json
{
  "query_title": "1",
  "movie": {
    "movie_id": 1,
    "title": "기생충",
    "predicted_rating": 8.8
  },
  "recommendations": [
    {
      "movie_id": 2,
      "title": "추천영화A",
      "predicted_rating": 8.8,
      "personalization_score": 0.41,
      "final_score": 6.04
    }
  ]
}
```

## 7) 점검 체크리스트

- [ ] `POST /analyze/id`가 `movie_id` 필수값을 검증하는가
- [ ] 존재하지 않는 ID 입력 시 `404`를 반환하는가
- [ ] 정상 입력 시 기존 `/analyze`와 동일 응답 구조를 반환하는가
- [ ] `top_k`가 1~10 범위에서 정상 동작하는가
- [ ] `user_history` 포함/미포함 모두 정상 동작하는가

