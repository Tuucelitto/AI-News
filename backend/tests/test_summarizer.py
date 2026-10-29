from typing import Any

import httpx
import pytest
from google.genai import errors, types

from app.services.summarizer import (
    ArticleInput,
    ArticleSummary,
    BatchSummary,
    GeminiSummarizer,
    PermanentSummaryError,
    TransientSummaryError,
    build_prompt,
)

ARTICLES = [
    ArticleInput(id=1, title="New model released", text="A lab released a new model."),
    ArticleInput(id=2, title="Chip demand grows", text="Demand for AI chips keeps growing."),
]


class FakeModels:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeClient:
    """Stands in for genai.Client: only `client.models.generate_content` is used."""

    def __init__(self, result: Any) -> None:
        self.models = FakeModels(result)


def summary(article_id: int) -> ArticleSummary:
    return ArticleSummary(
        article_id=article_id,
        title_tr=f"Başlık {article_id}",
        summary_tr="Kısa bir özet.",
        key_points=["Önemli nokta"],
    )


def response_with(*summaries: ArticleSummary) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(parsed=BatchSummary(summaries=list(summaries)))


def quota_error(quota_id: str, retry_delay: str = "37s") -> errors.ClientError:
    return errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "You exceeded your current quota.",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{"quotaId": quota_id}],
                    },
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": retry_delay,
                    },
                ],
            }
        },
    )


def summarizer_for(result: Any) -> GeminiSummarizer:
    return GeminiSummarizer(client=FakeClient(result), model="test-model", max_input_chars=1000)


def test_returns_summaries_by_article_id() -> None:
    summarizer = summarizer_for(response_with(summary(1), summary(2)))

    result = summarizer.summarize(ARTICLES)

    assert set(result) == {1, 2}
    assert result[1].title_tr == "Başlık 1"


def test_skipped_and_unknown_ids_are_left_out() -> None:
    # The model forgot article 2 and invented article 99.
    summarizer = summarizer_for(response_with(summary(1), summary(99)))

    assert set(summarizer.summarize(ARTICLES)) == {1}


def test_request_contains_all_articles_and_structured_output_config() -> None:
    summarizer = summarizer_for(response_with(summary(1), summary(2)))

    summarizer.summarize(ARTICLES)

    (call,) = summarizer.client.models.calls
    assert call["model"] == "test-model"
    assert '<article id="1">' in call["contents"]
    assert '<article id="2">' in call["contents"]
    config = call["config"]
    assert config.response_schema is BatchSummary
    assert config.response_mime_type == "application/json"
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert "Turkish" in config.system_instruction


def test_empty_batch_makes_no_request() -> None:
    summarizer = summarizer_for(response_with())

    assert summarizer.summarize([]) == {}
    assert summarizer.client.models.calls == []


def test_long_text_is_truncated_at_a_word_boundary() -> None:
    article = ArticleInput(id=1, title="Long", text="word " * 1000)

    prompt = build_prompt([article], max_chars=100)

    assert "word " * 19 + "word […]" in prompt
    assert len(prompt) < 200


def test_rate_limit_is_transient_with_server_suggested_delay() -> None:
    summarizer = summarizer_for(quota_error("GenerateRequestsPerMinutePerProjectPerModel-FreeTier"))

    with pytest.raises(TransientSummaryError) as exc_info:
        summarizer.summarize(ARTICLES)

    assert exc_info.value.retry_after == 37.0
    assert exc_info.value.daily_quota_exhausted is False


def test_daily_quota_is_recognized() -> None:
    summarizer = summarizer_for(quota_error("GenerateRequestsPerDayPerProjectPerModel-FreeTier"))

    with pytest.raises(TransientSummaryError) as exc_info:
        summarizer.summarize(ARTICLES)

    assert exc_info.value.daily_quota_exhausted is True


@pytest.mark.parametrize(
    "error",
    [
        errors.ServerError(503, {"error": {"code": 503, "message": "Model overloaded"}}),
        httpx.ReadTimeout("timed out"),
    ],
)
def test_server_errors_and_timeouts_are_transient(error: Exception) -> None:
    with pytest.raises(TransientSummaryError) as exc_info:
        summarizer_for(error).summarize(ARTICLES)

    assert exc_info.value.retry_after is None


def test_bad_request_is_permanent() -> None:
    error = errors.ClientError(400, {"error": {"code": 400, "message": "Invalid argument"}})

    with pytest.raises(PermanentSummaryError, match="400"):
        summarizer_for(error).summarize(ARTICLES)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            types.GenerateContentResponse(
                prompt_feedback=types.GenerateContentResponsePromptFeedback(
                    block_reason=types.BlockedReason.SAFETY
                )
            ),
            "blocked",
        ),
        (
            types.GenerateContentResponse(
                candidates=[types.Candidate(finish_reason=types.FinishReason.MAX_TOKENS)]
            ),
            "MAX_TOKENS",
        ),
    ],
)
def test_response_without_valid_summary_is_permanent(
    response: types.GenerateContentResponse, message: str
) -> None:
    with pytest.raises(PermanentSummaryError, match=message):
        summarizer_for(response).summarize(ARTICLES)


def test_missing_api_key_fails_early() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiSummarizer()
