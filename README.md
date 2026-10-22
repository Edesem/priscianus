# Priscianus

> *Noli caput Prisciani frangere!* ("Don't break Priscian's head!")

Named after Priscian (Priscianus Caesariensis), whose *Institutiones Grammaticae* was the standard Latin grammar for a thousand years. A grammatical error was once said to "break Priscian's head".

This is an AI integrated product, aimed at providing better tools for learning Latin grammar. Due to the lack of Latin data compared to English data, as well as the lack of Latin educated people, it is difficult to truly verify an LLMs output is actually correct. This product uses a morphology engine to confirm and verify answers that the LLM outputs.

## Plan

The current plan for this project can be referred to at [docs/plan.md](docs/plan.md).

## Getting started

Requires [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/) and [pre-commit](https://pre-commit.com/).

```sh
cp .env.example .env   # add your ANTHROPIC_API_KEY
make setup
make test
make lint
```

## Results

| Mode | Model | Accuracy | Cost / request |
|---|---|---|---|
| _TBD_ | | | |

## Licence

Code: MIT. Data is licensed separately; see [DATA_LICENCES.md](DATA_LICENCES.md).
