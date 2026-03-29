# ChessAdapt Benchmark — Results Report

## Model Comparison

| Rank | Model | Tier | Tasks | Compliance | Inhibition | Flexibility | **Composite** |
|:--:|:--|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | Llama 3 70B | mid | 500 | 0.030 | 1.000 | 1.000 | **0.515** |
| 2 | GPT-4o | frontier | 0 | 0.000 | 0.000 | 0.000 | **0.000** |

## Gradient Verification

**Status**: ⚠️ Not verified

- Frontier average: 0.000
- Mid-tier average: 0.515
- Weak-tier average: 0.000

## Per-Perturbation Breakdown

| Rule | Llama 3 70B |
|:--|:--:|
| bishop_as_rook | 0.030 |
| knight_two_squares | 0.000 |

## Difficulty Tier Breakdown

| Difficulty | Llama 3 70B |
|:--|:--:|
| Easy | — |
| Medium | 0.030 |
| Hard | — |

## Task Type Breakdown

| Task Type | Llama 3 70B |
|:--|:--:|
| T1 | 0.515 |
| T2 | — |
| T3 | — |