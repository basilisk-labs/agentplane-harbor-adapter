#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input_per_m: float
    cached_input_per_m: float
    output_per_m: float


@dataclass(frozen=True)
class TokenProfile:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


PRICES = {
    "gpt-5.5": Price(input_per_m=5.00, cached_input_per_m=0.50, output_per_m=30.00),
    "gpt-5.4": Price(input_per_m=2.50, cached_input_per_m=0.25, output_per_m=15.00),
    "gpt-5.4-mini": Price(input_per_m=0.75, cached_input_per_m=0.075, output_per_m=4.50),
    "gpt-5.4-nano": Price(input_per_m=0.20, cached_input_per_m=0.02, output_per_m=1.25),
    "gpt-5-nano": Price(input_per_m=0.05, cached_input_per_m=0.005, output_per_m=0.40),
}

PROFILES = {
    "low": TokenProfile(input_tokens=100_000, cached_input_tokens=25_000, output_tokens=15_000),
    "mid": TokenProfile(input_tokens=250_000, cached_input_tokens=75_000, output_tokens=50_000),
    "high": TokenProfile(input_tokens=600_000, cached_input_tokens=150_000, output_tokens=120_000),
}


def cost_for(tasks: int, price: Price, profile: TokenProfile) -> float:
    uncached_input = max(profile.input_tokens - profile.cached_input_tokens, 0)
    per_task = (
        uncached_input / 1_000_000 * price.input_per_m
        + profile.cached_input_tokens / 1_000_000 * price.cached_input_per_m
        + profile.output_tokens / 1_000_000 * price.output_per_m
    )
    return per_task * tasks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Estimate OpenAI API cost for Terminal-Bench runs."
    )
    parser.add_argument("--model", choices=PRICES.keys(), default="gpt-5-nano")
    parser.add_argument("--tasks", type=int, default=80)
    parser.add_argument("--profile", choices=PROFILES.keys(), default="mid")
    parser.add_argument("--input-tokens", type=int)
    parser.add_argument("--cached-input-tokens", type=int)
    parser.add_argument("--output-tokens", type=int)
    args = parser.parse_args()

    profile = PROFILES[args.profile]
    has_custom_tokens = (
        args.input_tokens is not None
        or args.cached_input_tokens is not None
        or args.output_tokens is not None
    )
    if has_custom_tokens:
        profile = TokenProfile(
            input_tokens=(
                args.input_tokens if args.input_tokens is not None else profile.input_tokens
            ),
            cached_input_tokens=(
                args.cached_input_tokens
                if args.cached_input_tokens is not None
                else profile.cached_input_tokens
            ),
            output_tokens=(
                args.output_tokens if args.output_tokens is not None else profile.output_tokens
            ),
        )

    total = cost_for(args.tasks, PRICES[args.model], profile)
    print(f"model={args.model}")
    print(f"tasks={args.tasks}")
    print(f"profile={args.profile}")
    print(f"input_tokens_per_task={profile.input_tokens}")
    print(f"cached_input_tokens_per_task={profile.cached_input_tokens}")
    print(f"output_tokens_per_task={profile.output_tokens}")
    print(f"estimated_total_usd=${total:,.2f}")
    print(f"estimated_per_task_usd=${total / args.tasks:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
