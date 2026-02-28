"""
crash_analyzer/analyzer.py

System Prompt 直注法：将完整诊断知识库塞入 system prompt。

依赖安装：
  pip install requests
"""


import json
import requests

from knowledge_base import SYSTEM_PROMPT


# ─────────────────────────────────────────────
#  配置项
# ─────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL   = "qwen3:4b"   # 换成你本地已 pull 的模型名


# ─────────────────────────────────────────────
#  工具函数
# ─────────────────────────────────────────────
def _post(endpoint: str, payload: dict, stream: bool = False, timeout: int = 12000):
    """统一的 Ollama HTTP 请求封装"""
    url = f"{OLLAMA_BASE_URL}{endpoint}"
    try:
        resp = requests.post(url, json=payload, stream=stream, timeout=timeout)
        resp.raise_for_status()
        return resp
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"无法连接 Ollama（{OLLAMA_BASE_URL}）\n"
            "请先执行：ollama serve"
        )


def list_models() -> list[str]:
    """列出本地所有可用模型"""
    resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]


def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    stream: bool = True,
    temperature: float = 0.1,   # 诊断任务使用低温度，减少随机性
    json_mode: bool = False,    # 强制JSON输出（如果模型支持）
) -> str:
    """
    调用 Ollama /api/chat，支持流式输出。
    messages 格式：[{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    payload = {
        "think": False,
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {"temperature": temperature},
    }
    
    # 启用JSON模式（如果模型支持）
    if json_mode:
        payload["format"] = "json"
    
    resp = _post("/api/chat", payload, stream=stream)

    full_text = ""
    if stream:
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            token = chunk.get("message", {}).get("content", "")
            think_token = chunk.get("message", {}).get("thinking", "")
            print(token, end="", flush=True)
            print(think_token, end="", flush=True)
            full_text += token
            if chunk.get("done"):
                break
        print()  # 换行
    else:
        full_text = resp.json()["message"]["content"]

    return full_text


# ─────────────────────────────────────────────
#  Mode 1：System Prompt 直注法
# ─────────────────────────────────────────────
class SystemPromptAnalyzer:
    """
    将完整诊断知识库塞入 system prompt。
    优点：零额外依赖，对话历史中始终携带知识。
    适合：规则数量 < 50 条，知识文本 < 8K tokens。
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._system_msg = {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
        print(f"[SystemPromptAnalyzer] 使用模型: {self.model}")
        print(f"[SystemPromptAnalyzer] 知识注入长度: {len(SYSTEM_PROMPT)} 字符")

    def analyze(self, crash_log: str, stream: bool = True, json_mode: bool = True) -> str:
        """分析单条崩溃日志"""
        user_msg = {
            "role": "user",
            "content": (
                "The log to analyze is as follows, output the crash fingerprint in JSON format:\n\n"
                "```\n"
                f"{crash_log.strip()}\n"
                "```"
            ),
        }
        print(f"\n{'='*60}")
        print(f"[分析中] 模型: {self.model}")
        print(f"[分析中] JSON模式: {json_mode}")
        print(f"{'='*60}\n")
        return chat([self._system_msg, user_msg], model=self.model, stream=stream, json_mode=json_mode)

    def batch_analyze(self, crash_logs: list[str]) -> list[dict]:
        """
        批量分析多条日志，每条独立请求（无上下文污染）。
        返回结构化结果列表。
        """
        results = []
        for i, log in enumerate(crash_logs, 1):
            print(f"\n[{i}/{len(crash_logs)}] 正在分析...")
            answer = self.analyze(log, stream=False)
            results.append({
                "index": i,
                "crash_log": log[:200] + "..." if len(log) > 200 else log,
                "analysis": answer,
            })
        return results