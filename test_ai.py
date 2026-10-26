"""Offline tests for ai_explanation.py (Groq). HTTP calls are mocked; no key needed."""

import os
from unittest.mock import MagicMock, patch

import requests

import ai_explanation as ai
from health_score import calculate_health_score
from nutrient_parser import parse_nutrients

PARSED = parse_nutrients("Per 100 g\nEnergy 450 kcal\nProtein 8 g\nSugars 18 g\nSaturated Fat 6 g\nFibre 4 g\nSodium 400 mg")
SCORE = calculate_health_score(PARSED)


def _env(**kw):
    base = {"GROQ_API_KEY": "", "GROQ_MODEL": ""}
    base.update(kw)
    ai._WORKING_MODEL.clear()
    return patch.dict(os.environ, base)


def _reply(status, body=None):
    fake = MagicMock(); fake.status_code = status; fake.text = ""
    fake.json.return_value = body if body is not None else {}
    return fake


def _ok(text="Nice summary."):
    return _reply(200, {"choices": [{"message": {"content": text}}]})


def test_no_key_uses_template():
    with _env():
        text, src = ai.explain_score(PARSED, SCORE, "Snacks")
    assert src.startswith("Template") and "no Groq API key" in src
    assert f"{SCORE['score']}/100" in text and SCORE["category"] in text


def test_prompt_contains_score_and_rules():
    p = ai.build_prompt(PARSED, SCORE, "Snacks")
    assert f"{SCORE['score']}/100" in p and "Do NOT change" in p and "Sugars: 18 g" in p


def test_success_uses_groq_endpoint_and_bearer_key():
    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", return_value=_ok(" Nice summary. ")) as post:
        text, src = ai.explain_score(PARSED, SCORE)
    assert text == "Nice summary." and src == "AI (Groq)"
    assert post.call_args.args[0] == "https://api.groq.com/openai/v1/chat/completions"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer gsk_k"
    assert post.call_args.kwargs["json"]["model"] == "llama-3.3-70b-versatile"


def test_custom_model_is_used_first():
    with _env(GROQ_API_KEY="gsk_k", GROQ_MODEL="my-model"), patch.object(ai.requests, "post", return_value=_ok()) as post:
        ai.explain_score(PARSED, SCORE)
    assert post.call_args.kwargs["json"]["model"] == "my-model"


def test_key_with_quotes_and_spaces_is_cleaned():
    with _env(GROQ_API_KEY='  "gsk_k"  '), patch.object(ai.requests, "post", return_value=_ok()) as post:
        ai.explain_score(PARSED, SCORE)
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer gsk_k"


def test_network_error_falls_back():
    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", side_effect=requests.exceptions.ConnectionError("x")):
        text, src = ai.explain_score(PARSED, SCORE)
    assert src.startswith("Template (AI unavailable") and "could not connect" in src and text


def test_bad_response_falls_back():
    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", return_value=_reply(200, {"unexpected": 1})):
        text, src = ai.explain_score(PARSED, SCORE)
    assert src.startswith("Template (AI unavailable") and "unexpected reply" in src


def test_empty_answer_falls_back():
    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", return_value=_ok("   ")):
        text, src = ai.explain_score(PARSED, SCORE)
    assert src.startswith("Template (AI unavailable") and "nothing" in src


def test_no_score_no_explanation():
    assert ai.explain_score(PARSED, {"score": None}) == ("", "none")


def test_rejected_key_stops_immediately_with_a_clear_reason():
    with _env(GROQ_API_KEY="gsk_bad"), patch.object(ai.requests, "post", return_value=_reply(401, {"error": {"message": "Invalid API Key"}})) as post:
        text, src = ai.explain_score(PARSED, SCORE)
    assert "key was rejected (401)" in src and "console.groq.com/keys" in src and text
    assert post.call_count == 1                                     # other models cannot fix a refused key


def test_busy_model_falls_through_to_the_fast_fallback_model():
    def fake_post(url, **kwargs):
        if kwargs["json"]["model"] == "llama-3.3-70b-versatile":
            return _reply(429, {"error": {"message": "rate limit"}})
        return _ok("Answered by the fallback model.")

    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", side_effect=fake_post):
        text, src = ai.explain_score(PARSED, SCORE)
    assert text == "Answered by the fallback model." and src == "AI (Groq)"
    assert ai._WORKING_MODEL["groq"] == "llama-3.1-8b-instant"


def test_timeout_on_first_model_tries_the_next():
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs["json"]["model"])
        if len(calls) == 1:
            raise requests.exceptions.Timeout()
        return _ok("Second try worked.")

    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", side_effect=fake_post):
        text, src = ai.explain_score(PARSED, SCORE)
    assert text == "Second try worked." and len(calls) == 2


def test_retired_models_are_replaced_from_groqs_model_list():
    listing = _reply(200, {"data": [{"id": "whisper-large-v3", "active": True}, {"id": "llama-9-instant", "active": True},
                                    {"id": "llama-guard-9", "active": True}, {"id": "llama-9-versatile", "active": False}]})

    def fake_post(url, **kwargs):
        if kwargs["json"]["model"] == "llama-9-instant":
            return _ok("Works.")
        return _reply(400, {"error": {"message": "The model `x` has been decommissioned and is no longer supported."}})

    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", side_effect=fake_post), patch.object(ai.requests, "get", return_value=listing):
        text, src = ai.explain_score(PARSED, SCORE)
    assert text == "Works." and src == "AI (Groq)" and ai._WORKING_MODEL["groq"] == "llama-9-instant"


def test_discovery_includes_non_llama_models_and_skips_non_chat_ones():
    listing = _reply(200, {"data": [{"id": "llama-3.1-8b-instant"}, {"id": "some-new/model-x"}, {"id": "openai/gpt-oss-20b"},
                                    {"id": "whisper-large-v3"}, {"id": "llama-guard-4"}, {"id": "playai-tts"},
                                    {"id": "groq/compound"}, {"id": "llama-3.3-70b-versatile"}]})
    with patch.object(ai.requests, "get", return_value=listing):
        assert ai.discover_models("k") == ["openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "some-new/model-x"]


def test_when_all_llama_models_are_gone_a_newer_model_is_found():
    listing = _reply(200, {"data": [{"id": "newfamily/chat-1"}, {"id": "whisper-large-v3"}]})

    def fake_post(url, **kwargs):
        if kwargs["json"]["model"] == "newfamily/chat-1":
            return _ok("New model answered.")
        return _reply(404, {"error": {"message": "The model does not exist or you do not have access to it."}})

    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", side_effect=fake_post), patch.object(ai.requests, "get", return_value=listing):
        text, src = ai.explain_score(PARSED, SCORE)
    assert text == "New model answered." and src == "AI (Groq)"


def test_gpt_oss_gets_low_reasoning_and_think_blocks_are_removed():
    seen = {}

    def fake_post(url, **kwargs):
        seen.update(kwargs["json"])
        return _ok("<think>hidden</think>Visible answer.")

    with _env(GROQ_API_KEY="gsk_k", GROQ_MODEL="openai/gpt-oss-20b"), patch.object(ai.requests, "post", side_effect=fake_post):
        text, src = ai.explain_score(PARSED, SCORE)
    assert seen["reasoning_effort"] == "low" and text == "Visible answer."


def test_all_models_missing_gives_a_clear_reason():
    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", return_value=_reply(404, {"error": {"message": "not found"}})), \
            patch.object(ai.requests, "get", return_value=_reply(200, {"data": []})):
        text, src = ai.explain_score(PARSED, SCORE)
    assert src.startswith("Template (AI unavailable") and "no Groq model worked" in src and "Groq said: not found" in src
    assert "none listed" in src and text


def test_rate_limit_everywhere_is_reported():
    with _env(GROQ_API_KEY="gsk_k"), patch.object(ai.requests, "post", return_value=_reply(429, {"error": {"message": "quota"}})):
        text, src = ai.explain_score(PARSED, SCORE)
    assert "usage limit" in src and "429" in src and text


def test_key_status_reports_shape_but_never_the_key():
    with _env(GROQ_API_KEY='"gsk_SecretValue"'):
        assert ai.key_status() == [("Groq", "GROQ_API_KEY found")]
    with _env(GROQ_API_KEY="AIzaWrongKind"):
        (label, status), = ai.key_status()
        assert "doesn't start with gsk_" in status and "AIzaWrongKind" not in status
    with _env():
        assert ai.key_status() == [("Groq", "GROQ_API_KEY not found")]
