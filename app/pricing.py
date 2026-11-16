"""Deterministic pricing table and cost calculator for LLM token usage."""

LLM_PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    # model: (input_cost_usd_per_1m, output_cost_usd_per_1m)
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "gemini-2.5-pro": (1.25, 5.00),
    "gemini-2.5-flash": (0.075, 0.30),
}

DEFAULT_LLM_PRICING: tuple[float, float] = (1.00, 3.00)


def calculate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate deterministic estimated USD cost based on token consumption.

    Args:
        model: Identifier of the language model (case-insensitive).
        input_tokens: Number of prompt tokens.
        output_tokens: Number of completion tokens.

    Returns:
        Calculated cost in USD rounded to 6 decimal places (minimum 0.000001).
    """
    normalized_model = model.strip().lower()
    input_rate, output_rate = LLM_PRICING_PER_MILLION.get(
        normalized_model, DEFAULT_LLM_PRICING
    )
    raw_cost = (
        (input_tokens * input_rate) + (output_tokens * output_rate)
    ) / 1_000_000.0

    return max(round(raw_cost, 6), 0.000001)
