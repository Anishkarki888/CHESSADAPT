# ChessAdapt: Rule-Perturbed Chess Benchmark

A benchmark that measures **cognitive flexibility** and **inhibitory control** in frontier LLMs by perturbing the rules of chess, the most memorized game domain in AI training data.

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
make install

# Run tests
make test

# Full pipeline
make data          # Extract 500 positions from Lichess
make tasks         # Generate T1/T2/T3 benchmark tasks
make evaluate MODEL=gpt-4o   # Evaluate a model
make analyze       # Produce results report
```

## Perturbation Engine

The engine provides 8 rule perturbations across three categories:

| Category | Rule | Difficulty |
|:--|:--|:--:|
| Movement | Bishop moves like Rook | Medium |
| Movement | Knight moves 2 squares (no L-shape) | Hard |
| Movement | Queen cannot move backwards | Easy |
| Movement | Pawns capture forward (not diagonal) | Hard |
| Win Condition | Capture all opponent pawns to win | Easy |
| Win Condition | First to reach e4/e5 wins | Medium |
| Turn Structure | Two moves per turn | Hard |
| Turn Structure | Cannot move same piece twice in a row | Medium |

### Single Rule

```python
from engine.registry import get_board

board = get_board("bishop_as_rook", fen)
print(list(board.legal_moves))
```

### Stacked Rules (T3)

```python
from engine.composition import RuleComposer

composer = RuleComposer(fen, ["bishop_as_rook", "no_repeat_piece"])
print(composer.legal_uci_moves())
print(composer.rule_delta())
```

## Evaluation Pipeline

### Configure API Keys

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
export OPENROUTER_API_KEY="sk-or-v1-..."
```

### Run Evaluation

```bash
# Dry run (no API calls — test pipeline)
make dry-run

# Single model
make evaluate MODEL=gpt-4o

# All models
make evaluate-all

# Analyze results
make analyze
```

### Supported Models

| Model | Provider | Tier |
|:--|:--|:--:|
| GPT-4o | OpenAI | Frontier |
| GPT-4o Mini | OpenAI | Mid |
| Claude 3.7 Sonnet | Anthropic | Frontier |
| Gemini 2.5 Pro | Google | Frontier |
| Llama 3 70B | OpenRouter | Mid |
| Mistral Large | OpenRouter | Mid |

## Scoring

```
Composite = 0.50 × Compliance + 0.30 × Inhibition + 0.20 × Flexibility
```

- **Compliance Rate**: Fraction of moves legal under perturbed rules
- **Inhibition Score**: 1 − (fraction of standard-chess moves played when illegal)
- **Flexibility Index**: Compliance variance normalized across perturbation categories

## Makefile Targets

```bash
make help            # Show all targets
make install         # Install dependencies
make test            # Run all tests
make test-coverage   # Tests with coverage report
make data            # Generate positions.jsonl
make tasks           # Generate benchmark tasks
make evaluate        # Evaluate MODEL (default: gpt-4o)
make evaluate-all    # Evaluate all models
make dry-run         # Pipeline test (no API calls)
make analyze         # Produce results report
make clean           # Remove generated data
```

## Documentation

- [Engine Overview](engine/README.md)
- [Writeup & Methodology](docs/writeup.md)
- [Movement Rules](engine/rules/movement/README.md)
- [Win Condition Rules](engine/rules/win_conditions/README.md)
- [Turn Structure Rules](engine/rules/turn_structure/README.md)

## Testing

```bash
make test              # All tests (40+ test cases)
make test-composition  # Composition module only
make test-movement     # Movement rules only
make test-coverage     # With coverage report
```
