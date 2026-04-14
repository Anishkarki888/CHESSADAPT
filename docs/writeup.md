# ChessAdapt: Measuring Cognitive Flexibility Through Rule-Perturbed Chess

## Problem: Benchmarks Measure Knowledge, Not Adaptability

Current AI benchmarks test what models *know* — factual recall, reasoning on familiar patterns, and performance within well-studied domains. But the hallmark of general intelligence is not knowledge retrieval; it is the ability to **abandon** established knowledge when circumstances change and construct new strategies on the fly.

Chess is the ideal domain to expose this gap. Large language models ingest millions of chess games during training, absorbing opening theory, tactical motifs, and endgame patterns so deeply that responses become reflexive. When a model encounters a standard middlegame position, it fires a highly trained response — the "right" move according to centuries of human chess knowledge.

ChessAdapt exploits this directly. By **perturbing the rules of chess** — altering how pieces move, changing win conditions, and modifying turn structure — we force models to suppress their internalized game tree and reason under novel constraints. A model that cannot inhibit its memorized priors will play standard-chess moves that are now *illegal*. A model that cannot flexibly adapt will fail as perturbation complexity increases.

This benchmark targets critical cognitive faculties from the framework for measuring progress toward AGI: 
1. **Executive Functions**: Specifically **inhibitory control** (suppressing dominant but now-incorrect responses), **cognitive flexibility** (switching between rule sets), and **working memory** (compositional reasoning across sequences).
2. **Metacognition**: Specifically **monitoring** (confidence calibration and error detection) and **knowledge boundary awareness** (prospective difficulty judgment).

## Benchmark Design

### Task Taxonomy

ChessAdapt defines three task types of increasing cognitive demand:

| Task | Setup | Scoring | Cognitive Load |
|:--:|:--|:--|:--|
| **T1** | Single rule change, produce one move | Binary: legal or not | Low — rule comprehension |
| **T2** | Single rule change, produce best move | Legal rate + engine eval | Medium — comprehension + strategy |
| **T3** | 2–3 stacked rule changes, 3-move sequence | Per-move compliance × coherence | High — multi-rule reasoning |

### Metacognitive Probing

ChessAdapt doesn't just score the moves; it probes the model’s internal state. Every task includes a **Metacognitive Response Block** where the model must report its confidence (1-10) and predict whether its move was legal BEFORE receiving feedback. This allows us to calculate:
- **Calibration Error**: The distance between stated confidence and actual correctness.
- **Overconfidence Ratio**: How often a model plays an illegal move with high confidence (>=8/10).
- **In-Context Monitoring**: The accuracy of the model's YES/NO prediction of its own move's legality.

### Perturbation Catalogue

All positions are drawn from real Lichess games (1800–2400 Elo, moves 15–35) to ensure non-synthetic, non-gameable inputs. Eight perturbation types span three categories:

**Movement perturbations** alter how pieces move: bishops that slide orthogonally like rooks, knights that move exactly two squares in any direction instead of the L-shape, queens that cannot retreat, and pawns that capture forward instead of diagonally.

**Win condition perturbations** change the objective: capture all opponent pawns to win (checkmate disabled), or race to place a piece on e4/e5 first.

**Turn structure perturbations** modify the flow of play: two moves per turn instead of one, or a restriction preventing the same piece from moving on consecutive turns.

This catalogue is designed so that standard-chess best moves frequently become *illegal* under the perturbation, creating maximum inhibitory pressure.

### Scoring System

The composite score combines three metrics with weights calibrated to prioritize compliance while rewarding inhibition and flexibility:

**Composite Score = 0.50 × Compliance + 0.30 × Inhibition + 0.20 × Flexibility**

- **Compliance Rate** (50%): Fraction of model moves that are legal under the perturbed ruleset. The primary signal.
- **Inhibition Score** (30%): One minus the fraction of moves that exploit old standard-chess rules — directly measures failure to suppress the memorized prior.
- **Flexibility Index** (20%): Compliance variance normalized across perturbation categories. A flexible model maintains performance across movement, win-condition, and turn-structure changes.

### Gradient Engineering

The benchmark produces a performance gradient rather than a ceiling or floor. Three difficulty tiers ensure discriminatory power:

- **Easy**: Single rule, open middlegame, many legal alternatives. Multiple moves satisfy both old and new rules.
- **Medium**: Single rule, tactical positions. Standard-chess best move is now illegal.
- **Hard**: Stacked rules, tactical crisis, 3-move sequence required. Old-rule move is a discovered check or decisive tactic — maximum inhibitory pressure.

## Dataset Construction

### Source Data

Positions are extracted from the Lichess Open Database via Hugging Face streaming. We filter for games between 1800–2400 Elo players and extract board states from moves 15–35 (the middlegame window with maximum strategic complexity). Positions are deduplicated by canonical FEN to produce exactly **500 unique positions**.

### Task Generation Pipeline

Each position is paired with perturbation(s) and assigned a difficulty tier based on the position's tactical features and the perturbation's inhibitory pressure. The full pipeline generates:

- **200 T1 tasks** — single rule, binary compliance check
- **200 T2 tasks** — single rule, strategic quality evaluation  
- **100 T3 tasks** — 2–3 stacked rules from different categories, 3-move sequences

The `python-chess` library serves as the core engine, with each perturbation implemented as a `PerturbedBoard` subclass that overrides move generation, win condition checks, or turn management at the lowest level. A `RuleComposer` class handles multi-rule stacking by intersecting legal-move sets across movement rules while OR-combining win conditions.

## Evaluation Architecture

Models receive a structured prompt containing the board position (FEN + ASCII diagram), a natural-language description of the rule change(s), and explicit instructions to produce UCI-format moves. The evaluation pipeline supports five frontier models:

- **GPT-4o** and **GPT-4o Mini** (OpenAI)
- **Claude 3.7 Sonnet** (Anthropic)
- **Gemini 2.5 Pro** (Google)
- **Llama 3 70B** and **Mistral Large** (via OpenRouter)

Each model's response is parsed for UCI moves, validated against the composed perturbation ruleset, and scored using the three-metric composite. Results are persisted as structured JSON with full event traces — every move is logged with its legality status under both perturbed and standard rules, enabling post-hoc inhibition analysis.

The evaluation runner supports checkpoint-based resume, dry-run mode for pipeline validation, and batch processing across all models.

## Results

Results are organized as a model comparison table, per-perturbation breakdown, difficulty-tier analysis, and a gradient verification check. The gradient verification confirms that frontier models outperform mid-tier models, which in turn outperform weaker baselines — establishing the benchmark's discriminatory power as required by the competition criteria.

Key findings we expect to observe:

1. **Movement perturbations** produce the highest inhibition failure rate — models reflexively play standard piece movements
2. **T3 stacked-rule tasks** show the steepest performance drop, isolating cognitive flexibility as the bottleneck
3. **Compliance degrades monotonically** with difficulty tier across all models, confirming the gradient design

## Reproducibility

The entire pipeline is reproducible from a single command sequence:

```bash
make install     # Install dependencies
make data        # Extract 500 positions from Lichess
make tasks       # Generate T1/T2/T3 benchmark tasks
make evaluate-all  # Run all models
make analyze     # Produce results report
```

All code, data, and results are versioned and documented. The perturbation engine includes a full test suite (`pytest engine/tests/ -v`) validating each rule's legal-move generation against known expected outputs.

## Conclusion

ChessAdapt demonstrates that benchmark design can go beyond testing what models know to testing how models *adapt*. By leveraging chess as a maximally memorized domain and systematically perturbing its rules, we create a controlled environment where the difference between retrieval and reasoning becomes measurable. The three-metric composite — compliance, inhibition, and flexibility — provides a nuanced signal that a single accuracy number cannot. If a model scores highly on ChessAdapt, it is not because it memorized more chess — it is because it can *think past* what it memorized.
