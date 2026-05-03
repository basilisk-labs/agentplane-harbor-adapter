# Cost Guide

## Pricing basis

OpenAI standard API pricing checked on 2026-05-03:

| Model | Input | Cached input | Output |
| --- | ---: | ---: | ---: |
| GPT-5.5 | $5.00 / 1M tokens | $0.50 / 1M tokens | $30.00 / 1M tokens |
| GPT-5.4 | $2.50 / 1M tokens | $0.25 / 1M tokens | $15.00 / 1M tokens |
| GPT-5.4 mini | $0.75 / 1M tokens | $0.075 / 1M tokens | $4.50 / 1M tokens |

Terminal-Bench leaderboard dataset `terminal-bench-core==0.1.1` contains 80
tasks. The exact cost depends on agent turns, tool output volume, retry behavior,
and whether provider-side caching applies.

## Rough full-run estimates for 80 tasks

Assumptions are per task.

| Profile | Input/task | Cached input/task | Output/task | GPT-5.5 | GPT-5.4 | GPT-5.4 mini |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| low | 100k | 25k | 15k | ~$67 | ~$34 | ~$10 |
| mid | 250k | 75k | 50k | ~$193 | ~$97 | ~$29 |
| high | 600k | 150k | 120k | ~$474 | ~$237 | ~$71 |

These are planning estimates, not guarantees. Terminal tasks can become more
expensive when an agent repeatedly inspects large files, retries failing commands,
or prints verbose logs into context.

## Recommended budget path

1. Run `N=1` smoke.
2. Run `N=5` slice.
3. Estimate observed tokens/cost from provider usage.
4. Only then run all 80 tasks.

For leaderboard proof, avoid changing benchmark timeouts to reduce cost. If cost
needs to be controlled, use a cheaper model for adapter validation, then run the
official target model once.
