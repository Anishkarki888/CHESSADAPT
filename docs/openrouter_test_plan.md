# Implementation Plan: OpenRouter Evaluation

This plan outlines the steps to evaluate the 5 core models using the OpenRouter API key.

## 1. Prerequisites
Ensure you have `uv` installed. If not, install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`.

## 2. Setup Environment
First, install the necessary dependencies (OpenAI and Anthropic clients):
```bash
make install
```

Export your OpenRouter API key so the runner can access it:
```bash
export OPENROUTER_API_KEY="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"
```

## 3. Configured Models
The following models are now configured to use OpenRouter:
1.  **GPT-4o**: `gpt-4o-or`
2.  **Claude 3.7 Sonnet**: `claude-3.7-sonnet-or`
3.  **Llama 3 70B**: `llama-3-70b`
4.  **Mistral Large**: `mistral-large`
5.  **Qwen 2.5 72B**: `qwen-2.5-72b`

## 4. Execution
To run the full evaluation suite for these 5 models, run:
```bash
make evaluate-hackathon
```

This will:
- Load the 500 benchmark tasks.
- Sequentially call each model via OpenRouter.
- Save structured results to `data/results/<model_key>`.
- Parse both UCI moves and Metacognition probes.

## 5. Analysis
Once the evaluation is complete, generate the final report:
```bash
make analyze
```

This will produce a markdown report in `data/results/report.md` comparing the performance, inhibition failure rates, and metacognitive calibration across all 5 models.
