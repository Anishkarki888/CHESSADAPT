# ChessAdapt Benchmark — Results Report

## Model Comparison

| Rank | Model | Tier | Tasks | Compliance | Inhibition | Flexibility | **Composite** |
|:--:|:--|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | Claude 3.7 Sonnet (OpenRouter) | frontier | 100 | 0.553 | 0.983 | 1.000 | **0.772** |
| 2 | GPT-4o (OpenRouter) | frontier | 100 | 0.513 | 0.947 | 1.000 | **0.741** |
| 3 | Qwen 2.5 72B | mid | 100 | 0.165 | 1.000 | 1.000 | **0.583** |
| 4 | Llama 3 70B | mid | 99 | 0.108 | 1.000 | 1.000 | **0.554** |
| 5 | Mistral Large | mid | 0 | 0.000 | 0.000 | 0.000 | **0.000** |

## Gradient Verification

**Status**: ✅ Verified

- Frontier average: 0.756
- Mid-tier average: 0.379
- Weak-tier average: 0.000

## Per-Perturbation Breakdown

| Rule | Claude 3.7 Sonnet (OpenRouter) | GPT-4o (OpenRouter) | Llama 3 70B | Qwen 2.5 72B |
|:--|:--:|:--:|:--:|:--:|
| bishop_as_rook | 0.444 | 0.654 | 0.127 | 0.170 |
| capture_all_pawns | 0.565 | 0.578 | 0.014 | 0.095 |
| centre_race | 0.435 | 0.458 | 0.167 | 0.167 |
| knight_two_squares | 0.667 | 0.464 | 0.063 | 0.147 |
| no_repeat_piece | 0.510 | 0.585 | 0.149 | 0.112 |
| pawn_forward_capture | 0.706 | 0.647 | 0.163 | 0.248 |
| queen_no_backwards | 0.562 | 0.614 | 0.033 | 0.170 |
| two_moves_per_turn | 0.563 | 0.613 | 0.119 | 0.207 |

## Difficulty Tier Breakdown

| Difficulty | Claude 3.7 Sonnet (OpenRouter) | GPT-4o (OpenRouter) | Llama 3 70B | Qwen 2.5 72B |
|:--|:--:|:--:|:--:|:--:|
| Easy | 0.586 | 0.667 | 0.099 | 0.172 |
| Medium | 0.000 | 0.750 | 0.000 | 0.000 |
| Hard | 0.561 | 0.503 | 0.104 | 0.168 |

## Task Type Breakdown

| Task Type | Claude 3.7 Sonnet (OpenRouter) | GPT-4o (OpenRouter) | Llama 3 70B | Qwen 2.5 72B |
|:--|:--:|:--:|:--:|:--:|
| T1 | 0.789 | 0.813 | 0.555 | 0.590 |
| T2 | 0.777 | 0.826 | 0.540 | 0.580 |
| T3 | 0.772 | 0.741 | 0.554 | 0.582 |

## Metacognition Analysis

| Model | Calibration Error ↓ | Error Detection ↑ | Overconfidence | Underconfidence |
|:--|:--:|:--:|:--:|:--:|
| Claude 3.7 Sonnet (OpenRouter) | 0.897 | 0.000 | 0.480 | 0.000 |
| GPT-4o (OpenRouter) | 0.737 | 0.140 | 0.500 | 0.000 |
| Llama 3 70B | 0.800 | 0.000 | 0.970 | 0.000 |
| Qwen 2.5 72B | 0.844 | 0.010 | 0.870 | 0.000 |