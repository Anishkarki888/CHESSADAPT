# ChessAdapt — Makefile
# Publication-grade build automation for the benchmark project.
#
# Usage:
#   make help        — show all available targets
#   make install     — install dependencies
#   make test        — run all tests
#   make data        — generate positions.jsonl
#   make tasks       — generate benchmark task items
#   make evaluate    — run evaluation (set MODEL= for specific model)
#   make analyze     — produce results report
#   make clean       — remove generated data

# ── Configuration ────────────────────────────────────────────────────────────
PYTHON       := uv run python
PYTEST       := uv run pytest

POSITIONS    := data/positions/positions.jsonl
TASKS        := data/tasks/t1_tasks.jsonl
RESULTS_DIR  := data/results
REPORT       := $(RESULTS_DIR)/report.md
WRITEUP      := docs/writeup.md

# Default model for single-model evaluation
MODEL        ?= gpt-4o

# Task counts
T1_COUNT     ?= 200
T2_COUNT     ?= 200
T3_COUNT     ?= 100

# ── Phony targets ────────────────────────────────────────────────────────────
.PHONY: help install test lint data tasks evaluate evaluate-all analyze \
        report clean clean-results clean-tasks clean-all dry-run \
        test-smoke test-eval test-engine test-coverage

# ── Help ─────────────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo ""
	@echo "  ChessAdapt Benchmark — Build Targets"
	@echo "  ═════════════════════════════════════"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Variables:"
	@echo "    MODEL=gpt-4o        Model to evaluate (default: gpt-4o)"
	@echo "    T1_COUNT=200        Number of T1 tasks (default: 200)"
	@echo "    T2_COUNT=200        Number of T2 tasks (default: 200)"
	@echo "    T3_COUNT=100        Number of T3 tasks (default: 100)"
	@echo ""

# ── Setup ────────────────────────────────────────────────────────────────────
install: ## Install all dependencies using uv
	uv sync --extra llm --extra dev
	@echo "✓ Dependencies installed"

# ── Testing ──────────────────────────────────────────────────────────────────
test: ## Run all tests
	$(PYTEST) -v
	@echo "✓ All tests passed"

test-smoke: ## Run quick smoke tests
	$(PYTEST) -m smoke -v

test-engine: ## Run chess engine rule tests
	$(PYTEST) -m engine -v

test-eval: ## Run evaluation pipeline tests
	$(PYTEST) -m eval -v

test-coverage: ## Run tests with coverage report
	$(PYTEST) --cov=engine --cov=evaluation --cov-report=term-missing -v

# ── Data Pipeline ────────────────────────────────────────────────────────────
$(POSITIONS):
	@mkdir -p data/positions
	$(PYTHON) -m pipeline.hf_loader_part2
	@echo "✓ Positions extracted to $(POSITIONS)"

data: $(POSITIONS) ## Generate positions.jsonl using streaming extractor

$(TASKS): $(POSITIONS)
	@mkdir -p data/tasks
	$(PYTHON) -m pipeline.run_pipeline --positions $(POSITIONS) --tasks-dir data/tasks --sample 3
	@echo "✓ Benchmark task items generated in data/tasks/"

tasks: $(TASKS) ## Generate T1/T2/T3 task files for Kaggle submission

dataset: data tasks ## Run the full pipeline: download data → generate all task files

zip-dataset: tasks ## Create a zip file of the generated task data for Kaggle
	zip -j dataset.zip data/tasks/t1_tasks.jsonl data/tasks/t2_tasks.jsonl data/tasks/t3_tasks.jsonl
	@echo "✓ Dataset zipped to dataset.zip"

# ── Evaluation ───────────────────────────────────────────────────────────────
evaluate: $(TASKS) ## Evaluate a single model (MODEL=gpt-4o)
	$(PYTHON) -m evaluation.runner --model $(MODEL) --tasks $(TASKS)
	@echo "✓ Evaluation complete for $(MODEL)"

evaluate-all: $(TASKS) ## Evaluate all configured models
	$(PYTHON) -m evaluation.runner --all-models --tasks $(TASKS)
	@echo "✓ All model evaluations complete"

dry-run: $(TASKS) ## Dry run (no API calls) to test pipeline
	$(PYTHON) -m evaluation.runner --model $(MODEL) --tasks $(TASKS) \
		--dry-run --max-tasks 5 -v
	@echo "✓ Dry run complete"

# ── Analysis & Reporting ─────────────────────────────────────────────────────
$(REPORT):
	$(PYTHON) -c "\
from evaluation.analysis import ResultsAnalyzer; \
analyzer = ResultsAnalyzer('$(RESULTS_DIR)'); \
path = analyzer.save_report('$(REPORT)'); \
print(f'✓ Report saved to {path}')"

analyze: $(REPORT) ## Generate results analysis report
	@cat $(REPORT)

report: analyze ## Alias for analyze

# ── Cleanup ──────────────────────────────────────────────────────────────────
clean-results: ## Remove evaluation results
	rm -rf $(RESULTS_DIR)
	@echo "✓ Results cleaned"

clean-tasks: ## Remove generated tasks
	rm -f $(TASKS)
	@echo "✓ Tasks cleaned"

clean-logs: ## Remove log files
	rm -rf data/logs
	@echo "✓ Logs cleaned"

clean: clean-results clean-tasks clean-logs ## Remove all generated data
	@echo "✓ All generated data cleaned"

clean-all: clean ## Remove everything including positions
	rm -f $(POSITIONS)
	rm -rf .pytest_cache
	rm -rf engine/__pycache__ evaluation/__pycache__
	rm -rf .venv
	@echo "✓ Full clean complete"

