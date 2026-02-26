# AGENTS.md

This is a Python-based IDE crash log analyzer using Ollama LLM for intelligent diagnosis.

## Project Overview

- **Language**: Python 3 (type hints required)
- **Purpose**: Analyze IDE crash logs (JetBrains, DevEco Studio) using LLM with knowledge injection
- **Architecture**: System Prompt mode (injects full knowledge base into system prompt)

## Build & Run Commands

### Running the Analyzer

```# Analyze default demo log
python main.py

# Batch analysis of all demo logs
python main.py --batch

# Analyze custom log text
python main.py --log "your crash log here"

# Analyze log file
python main.py --file /path/to/hs_err_pid1234.log

# Scan directory for log files
python main.py --dir /path/to/logs

# List available Ollama models
python main.py --list-models

# Use custom model
python main.py --model llama3:8b
```
# Use custom model
python main.py --model llama3:8b
```

### Dependencies

```bash
pip install requests
```

### Testing

No formal test suite exists. Run the demo logs in `main.py` to verify functionality:
```bash
python main.py --batch
```

## Code Style Guidelines

### File Structure

- **main.py**: CLI entry point, demo logs, argument parsing
- **analyzer.py**: Core analysis logic (SystemPromptAnalyzer, chat utilities)
- **knowledge_base.py**: Structured knowledge rules and system prompt text

### Naming Conventions

- **Classes**: PascalCase (e.g., `SystemPromptAnalyzer`)
- **Functions/Methods**: snake_case (e.g., `run_system_prompt_mode`, `_post`)
- **Variables**: snake_case (e.g., `crash_log`, `messages`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `OLLAMA_BASE_URL`, `DEFAULT_MODEL`)
- **Private members**: Leading underscore (e.g., `_post`, `_system_msg`)

### Import Ordering

1. Standard library imports
2. Third-party imports
3. Local module imports

```python
import re
import json
import requests

from knowledge_base import KNOWLEDGE_RULES, SYSTEM_KNOWLEDGE_TEXT
```

### Type Annotations

Required for all function signatures and complex types:

```python
def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    stream: bool = True,
    temperature: float = 0.1,
    json_mode: bool = False,
) -> str:
    ...
```

### Docstrings

Multi-line docstrings for all modules, classes, and public functions:

```python
"""
crash_analyzer/analyzer.py

System Prompt 直注法：将完整诊断知识库塞入 system prompt。
"""
```

### Error Handling

- Use specific exception types
- Provide helpful error messages
- Raise custom exceptions with context

```python
try:
    resp = requests.post(url, json=payload, stream=stream, timeout=timeout)
    resp.raise_for_status()
    return resp
except requests.exceptions.ConnectionError:
    raise ConnectionError(
        f"无法连接 Ollama（{OLLAMA_BASE_URL}）\n"
        "请先执行：ollama serve"
    )
```

### Comments & Formatting

- Use section dividers for major code blocks:
  ```python
  # ─────────────────────────────────────────────
  #  Mode 1：System Prompt 直注法
  # ─────────────────────────────────────────────
  ```

- 4-space indentation (standard Python)
- Line length: ~120 characters (flexible)
- Blank lines between functions and classes

### Knowledge Base Structure

Rules in `knowledge_base.py` must follow this schema:

```python
{
    "id": "UNIQUE_ID",
    "category": "类别名",
    "name": "规则名称",
    "keywords": ["keyword1", "keyword2", ...],
    "exception_types": ["ExceptionType", ...],
    "negative_keywords": ["exclude1", ...],  # Optional
    "platforms": ["windows", "mac", "darwin"],  # Optional
    "description": "详细描述",
    "solution": "解决方案（可包含\\n换行）",
}
```

## Architecture Patterns

### Analysis Mode

**SystemPromptAnalyzer**: Injects full knowledge into system prompt. Best for <50 rules.

### LLM Integration

- Uses Ollama HTTP API (`http://localhost:11434`)
- Default model: `qwen3:4b` (configurable via `--model` flag)
- Supports streaming output and JSON mode
- Low temperature (0.1) for deterministic analysis

### Configuration

Key constants in `analyzer.py`:
- `OLLAMA_BASE_URL`: Ollama server endpoint
- `DEFAULT_MODEL`: Default chat model
