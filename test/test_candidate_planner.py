from unittest.mock import patch

from automation.candidate_planner import evaluate, generate_ideas, score_candidate


def test_candidate_requires_real_visual_depth_to_score_high():
    idea = {"hook": "You see this every day.", "channel_fit_score": 95, "pexels_queries": ["q"] * 6}
    strong = score_candidate(
        idea, research=4,
        footage={"unique_video_count": 12, "successful_query_count": 6}, novelty=20,
    )
    weak = score_candidate(
        idea, research=2,
        footage={"unique_video_count": 2, "successful_query_count": 1}, novelty=20,
    )
    assert strong >= 75
    assert weak < 75


def test_builtwhys_rejects_model_invented_topics():
    payload = {"ideas": [
        {"topic": "Why bicycles have a one-tooth chainring", "pexels_queries": ["bike"] * 6},
        {"topic": "Why escalator steps have deep grooves", "pexels_queries": ["escalator"] * 6},
    ]}
    with patch("automation.candidate_planner._local_json", return_value=payload):
        ideas = generate_ideas("builtwhys", [])
    assert [idea["topic"] for idea in ideas] == ["Why escalator steps have deep grooves"]


def test_local_model_aliases_are_completed_before_candidate_validation():
    payload = {"ideas": [{
        "topic": "Why bottle caps have vertical ridges",
        "reason": "It explains a visible grip feature.",
        "queries": ["bottle cap close up"],
        "fit_score": "96",
    }]}
    with patch("automation.candidate_planner._local_json", return_value=payload):
        ideas = generate_ideas("builtwhys", [])
    assert len(ideas) == 1
    assert ideas[0]["fit_reason"]
    assert ideas[0]["channel_fit_score"] == 96
    assert len(ideas[0]["pexels_queries"]) == 6


def test_visual_puzzles_have_a_deterministic_best_candidate():
    ball = evaluate("visualwhys", {"topic": "Which Ball Reaches the Bottom First?"}, [])
    domino = evaluate("visualwhys", {"topic": "Which Domino Path Finishes First?"}, [])
    assert ball["pass"] and domino["pass"]
    assert ball["score"] > domino["score"]
