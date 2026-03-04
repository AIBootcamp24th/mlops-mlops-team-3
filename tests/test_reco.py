from src.reco.personalized import (
    CandidateMovie,
    RatedMovie,
    build_preference_vector,
    compute_final_score,
    personalization_score,
)


def test_personalization_score_prefers_user_taste() -> None:
    history = [
        RatedMovie(
            title="선호 영화",
            budget=100.0,
            runtime=120.0,
            popularity=80.0,
            vote_count=1000.0,
            rating=9.0,
        )
    ]
    candidates = [
        CandidateMovie(
            movie_id=1,
            title="취향 유사 영화",
            budget=110.0,
            runtime=118.0,
            popularity=79.0,
            vote_count=980.0,
            predicted_rating=7.0,
        ),
        CandidateMovie(
            movie_id=2,
            title="비유사 영화",
            budget=10.0,
            runtime=60.0,
            popularity=5.0,
            vote_count=10.0,
            predicted_rating=7.2,
        ),
    ]

    pref = build_preference_vector(history)
    near_score = personalization_score(candidates[0], pref)
    far_score = personalization_score(candidates[1], pref)

    assert near_score > far_score


def test_compute_final_score_includes_personalization() -> None:
    base = compute_final_score(predicted_rating=7.0, personalization=0.0)
    boosted = compute_final_score(predicted_rating=7.0, personalization=0.8)
    assert boosted > base
