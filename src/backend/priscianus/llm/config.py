"""Model IDs and prices. Every Claude call takes its model and its cost from here."""

from dataclasses import dataclass

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"


@dataclass(frozen=True)
class ModelPrice:
    """US dollars per million tokens."""

    input: float
    output: float

    @property
    def cache_read(self) -> float:
        return self.input * 0.1

    @property
    def cache_write(self) -> float:
        return self.input * 1.25


# Prices as of Oct 2026 (docs/plan.md section 8).
MODELS: dict[str, ModelPrice] = {
    HAIKU: ModelPrice(input=0.10, output=0.50),
    SONNET: ModelPrice(input=2.0, output=10.0),
    OPUS: ModelPrice(input=4.0, output=20.0),
}


def cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    price = MODELS[model]
    return (
        input_tokens * price.input
        + output_tokens * price.output
        + cache_read_tokens * price.cache_read
        + cache_write_tokens * price.cache_write
    ) / 1_000_000
