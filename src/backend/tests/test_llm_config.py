import pytest

from priscianus.llm.config import HAIKU, MODELS, OPUS, SONNET, cost_usd


def test_model_ids_are_the_claude_5_5_family():
    assert (HAIKU, SONNET, OPUS) == ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
    assert set(MODELS) == {HAIKU, SONNET, OPUS}


def test_sonnet_cost_uses_plan_prices():
    # $2 in / $10 out per million tokens, cached input $0.20.
    usd = cost_usd(
        SONNET, input_tokens=1_000_000, output_tokens=1_000_000, cache_read_tokens=1_000_000
    )
    assert usd == pytest.approx(2 + 10 + 0.20)


def test_cache_write_costs_more_than_fresh_input():
    fresh = cost_usd(HAIKU, input_tokens=1000)
    written = cost_usd(HAIKU, cache_write_tokens=1000)
    assert written == pytest.approx(fresh * 1.25)


def test_unknown_model_is_an_error():
    with pytest.raises(KeyError):
        cost_usd("gpt-4", input_tokens=1)
