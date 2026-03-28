"""
evaluation — LLM benchmark evaluation pipeline for ChessAdapt.

Public API
----------
LLMClient          : Abstract base for LLM API adapters.
OpenAIClient       : GPT-4o / GPT-4o-mini adapter.
AnthropicClient    : Claude 3.7 Sonnet adapter.
GoogleClient       : Gemini 2.5 Pro adapter.
OpenRouterClient   : Llama 3 / Mistral via OpenRouter.
PromptBuilder      : Constructs evaluation prompts from task items.
ResponseParser     : Extracts UCI moves from raw model output.
TaskGenerator      : Creates T1/T2/T3 benchmark tasks from positions.
BenchmarkRunner    : Orchestrates full model evaluation.
ResultsAnalyzer    : Post-evaluation analysis and reporting.
"""

from evaluation.llm_client import (
    LLMClient,
    OpenAIClient,
    AnthropicClient,
    GoogleClient,
    OpenRouterClient,
    MODEL_CONFIGS,
)
from evaluation.prompt_builder import PromptBuilder
from evaluation.response_parser import ResponseParser
from evaluation.task_generator import TaskGenerator
from evaluation.runner import BenchmarkRunner
from evaluation.analysis import ResultsAnalyzer

__all__ = [
    "LLMClient",
    "OpenAIClient",
    "AnthropicClient",
    "GoogleClient",
    "OpenRouterClient",
    "MODEL_CONFIGS",
    "PromptBuilder",
    "ResponseParser",
    "TaskGenerator",
    "BenchmarkRunner",
    "ResultsAnalyzer",
]
