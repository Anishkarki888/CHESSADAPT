# ChessAdapt: Rule-Perturbed Chess Benchmark

A publication-grade benchmark that measures **cognitive flexibility** and **inhibitory control** in frontier LLMs by perturbing the rules of chess — the most memorized game domain in AI training data.

## Project Structure

```
chess_benchmark/
├── engine/                  # Core perturbation engine (python-chess)
│   ├── base.py              # PerturbedBoard base class
│   ├── registry.py          # Rule name → class mapping
│   ├── validator.py         # Move validation (perturbed vs standard)
│   ├── legal_moves.py       # Cached legal move generation
│   ├── rules/               # 8 perturbation implementations
│   │   ├── movement/        # Bishop-as-rook, knight-2sq, queen-no-back, pawn-fwd-capture
│   │   ├── win_conditions/  # Capture-all-pawns, centre-race
│   │   └── turn_structure/  # Two-moves-per-turn, no-repeat-piece
│   ├── composition/         # Rule stacking, logging, experiment tracking
│   │   ├── composer.py      # RuleComposer — multi-rule stacking
│   │   ├── mixins.py        # LoggingMixin + StateTrackingMixin
│   │   ├── metrics.py       # Composite scoring (compliance, inhibition, flexibility)
│   │   └── experiment.py    # ExperimentRunner with JSON persistence
│   ├── tests/               # Test suite
│   └── utils/               # Board visualizer
├── evaluation/              # LLM benchmark evaluation pipeline
│   ├── llm_client.py        # GPT-4o, Claude, Gemini, Llama, Mistral adapters
│   ├── prompt_builder.py    # T1/T2/T3 prompt templates
│   ├── response_parser.py   # UFC move extraction from model output
│   ├── task_generator.py    # Task item creation from positions
│   ├── runner.py            # Benchmark orchestrator with checkpoint resume
│   └── analysis.py          # Results tables, gradient verification, reporting
├── pipeline/                # Data collection
│   └── hf_loader.py         # Lichess → positions.jsonl via Hugging Face
├── docs/                    # Documentation
│   └── writeup.md           # 1,500-word Kaggle competition writeup
├── data/                    # Generated data (gitignored)
│   ├── positions/           # 500 unique middlegame positions
│   ├── tasks/               # Generated benchmark task items
│   ├── results/             # Per-model evaluation results
│   └── logs/                # Structured log files
├── Makefile                 # Build automation
└── requirements.txt         # Python dependencies
```

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
export OPENROUTER_API_KEY="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"
x-ai/grok-4.1-fast
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
- [Kaggle Writeup](docs/writeup.md)
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