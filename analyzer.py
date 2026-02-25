"""
crash_analyzer/analyzer.py

两种知识注入方式：
  Mode 1 —— System Prompt 直注法（零依赖，推荐小知识库）
  Mode 2 —— RAG 检索增强法（向量相似度，推荐大知识库）

依赖安装：
  pip install requests numpy   # 基础
  pip install numpy            # RAG 模式需要（向量计算）
"""

import re
import json
import math
import time
import textwrap
from typing import Optional
import requests

from knowledge_base import KNOWLEDGE_RULES, SYSTEM_KNOWLEDGE_TEXT


# ─────────────────────────────────────────────
#  配置项
# ─────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL   = "qwen3:4b"   # 换成你本地已 pull 的模型名
EMBED_MODEL     = "nomic-embed-text"  # 用于 RAG 的嵌入模型（需 ollama pull）


# ─────────────────────────────────────────────
#  工具函数
# ─────────────────────────────────────────────
def _post(endpoint: str, payload: dict, stream: bool = False, timeout: int = 120):
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
            "content": SYSTEM_KNOWLEDGE_TEXT,
        }
        print(f"[SystemPromptAnalyzer] 使用模型: {self.model}")
        print(f"[SystemPromptAnalyzer] 知识注入长度: {len(SYSTEM_KNOWLEDGE_TEXT)} 字符")

    def analyze(self, crash_log: str, stream: bool = True, json_mode: bool = True) -> str:
        """分析单条崩溃日志"""
        user_msg = {
            "role": "user",
            "content": (
                "请分析以下崩溃日志，按照知识库中的诊断规则进行判断。\n\n"
                "【重要】你必须只输出纯 JSON 格式，不要输出任何其他文字、解释或 markdown 标记！\n\n"
                "崩溃日志：\n\n"
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


# ─────────────────────────────────────────────
#  Mode 2：RAG 检索增强法
# ─────────────────────────────────────────────
def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """纯 Python 余弦相似度（不依赖 numpy）"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_embedding(text: str, model: str = EMBED_MODEL) -> list[float]:
    """调用 Ollama 嵌入接口获取向量"""
    resp = _post("/api/embeddings", {"model": model, "prompt": text}, timeout=60)
    return resp.json()["embedding"]


class RAGAnalyzer:
    """
    RAG 检索增强法：
    1. 离线阶段：将知识规则转成向量，建本地索引
    2. 在线阶段：对崩溃日志取嵌入向量，检索 Top-K 最相关规则
    3. 将检索到的规则拼入 prompt，让模型聚焦作答

    优点：知识库可扩展到数千条，不受 context window 限制。
    要求：需要额外 pull 嵌入模型（ollama pull nomic-embed-text）
    """

    def __init__(
        self,
        chat_model: str = DEFAULT_MODEL,
        embed_model: str = EMBED_MODEL,
        top_k: int = 3,
    ):
        self.chat_model  = chat_model
        self.embed_model = embed_model
        self.top_k       = top_k
        self._index: list[dict] = []   # [{rule, embedding}, ...]

        print(f"[RAGAnalyzer] 对话模型: {chat_model}")
        print(f"[RAGAnalyzer] 嵌入模型: {embed_model}")
        print(f"[RAGAnalyzer] Top-K: {top_k}")
        self._build_index()

    # ── 离线：构建向量索引 ──────────────────────
    def _rule_to_text(self, rule: dict) -> str:
        """将规则对象序列化为可嵌入的文本"""
        kw = ", ".join(rule.get("keywords", []))
        ex = ", ".join(rule.get("exception_types", []))
        return (
            f"规则名称: {rule['name']}\n"
            f"类别: {rule['category']}\n"
            f"关键词: {kw}\n"
            f"异常类型: {ex}\n"
            f"描述: {rule['description']}"
        )

    def _build_index(self):
        """为每条知识规则生成嵌入向量并存入内存索引"""
        print(f"\n[RAG] 正在构建知识向量索引（共 {len(KNOWLEDGE_RULES)} 条规则）...")
        t0 = time.time()
        for rule in KNOWLEDGE_RULES:
            text = self._rule_to_text(rule)
            try:
                emb = _get_embedding(text, self.embed_model)
                self._index.append({"rule": rule, "embedding": emb, "text": text})
            except Exception as e:
                print(f"  [警告] 规则 '{rule['name']}' 嵌入失败: {e}")
        elapsed = time.time() - t0
        print(f"[RAG] 索引构建完成，耗时 {elapsed:.1f}s，成功 {len(self._index)} 条\n")

    # ── 在线：检索 + 生成 ──────────────────────
    def _retrieve(self, query: str, k: int = None) -> list[dict]:
        """检索与 query 最相似的 Top-K 规则"""
        k = k or self.top_k
        if not self._index:
            return []

        query_emb = _get_embedding(query, self.embed_model)
        scored = [
            {
                "rule": item["rule"],
                "text": item["text"],
                "score": _cosine_similarity(query_emb, item["embedding"]),
            }
            for item in self._index
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def _build_rag_prompt(self, crash_log: str, retrieved: list[dict]) -> str:
        """将检索结果拼装为 prompt 中的上下文"""
        context_parts = []
        for i, item in enumerate(retrieved, 1):
            rule = item["rule"]
            score = item["score"]
            context_parts.append(
                f"--- 相关规则 {i}（相似度 {score:.3f}）---\n"
                f"{item['text']}\n"
                f"处置建议: {rule.get('solution', '暂无')}"
            )
        context = "\n\n".join(context_parts)

        return (
            "你是一个IDE崩溃日志分析专家。以下是从知识库中检索到的相关诊断规则：\n\n"
            f"{context}\n\n"
            "---\n"
            "请根据以上规则分析下面的崩溃日志，输出：\n"
            "1. 根因类别（从规则中匹配，或标注「未明确」）\n"
            "2. 关键证据（从日志中摘录1-2个支撑结论的关键片段）\n"
            "3. 置信度（高/中/低）\n"
            "4. 处置建议（1-3条）\n\n"
            "崩溃日志：\n"
            "```\n"
            f"{crash_log.strip()}\n"
            "```"
        )

    def analyze(self, crash_log: str, stream: bool = True) -> str:
        """RAG 分析：检索 → 构建 prompt → 生成"""
        print(f"\n{'='*60}")
        print("[RAG] 正在检索相关规则...")
        retrieved = self._retrieve(crash_log)

        for item in retrieved:
            print(f"  ✓ {item['rule']['name']} (score={item['score']:.3f})")
        print(f"{'='*60}\n")

        prompt = self._build_rag_prompt(crash_log, retrieved)
        messages = [{"role": "user", "content": prompt}]
        return chat(messages, model=self.chat_model, stream=stream)

    def analyze_with_scores(self, crash_log: str) -> dict:
        """返回检索分数 + 分析结果（用于调试/评估）"""
        retrieved = self._retrieve(crash_log)
        answer = self.analyze(crash_log, stream=False)
        return {
            "crash_log": crash_log[:300],
            "retrieved_rules": [
                {"name": r["rule"]["name"], "score": r["score"]}
                for r in retrieved
            ],
            "analysis": answer,
        }


# ─────────────────────────────────────────────
#  规则引擎（可选：纯关键词预分类，加速 LLM）
# ─────────────────────────────────────────────
class RuleEnginePreFilter:
    """
    轻量级规则引擎：在调用 LLM 之前，用关键词匹配预判根因。
    可单独使用（高速、零成本），也可作为 LLM 的前置过滤器。
    """

    def prefilter(self, crash_log: str) -> Optional[dict]:
        """
        返回最匹配的规则 dict，或 None（无法确定）。
        优先级从上到下，第一个命中的规则胜出。
        """
        log_lower = crash_log.lower()

        for rule in KNOWLEDGE_RULES:
            # 检查负面关键词（排除条件）
            neg_kws = rule.get("negative_keywords", [])
            if any(nk.lower() in log_lower for nk in neg_kws):
                continue

            # 物理内存规则需要 Possible reasons 存在
            if rule["id"] == "PHYSICAL_OOM":
                if "possible reasons" not in log_lower:
                    continue

            # 命中关键词计数
            matched = sum(
                1 for kw in rule["keywords"] if kw.lower() in log_lower
            )

            # 至少命中2个关键词才认为匹配（防误判）
            threshold = max(2, len(rule["keywords"]) // 2)
            if matched >= threshold:
                return {
                    "rule": rule,
                    "matched_count": matched,
                    "total_keywords": len(rule["keywords"]),
                    "confidence": "高" if matched >= len(rule["keywords"]) * 0.7 else "中",
                }

        return None

    def format_result(self, result: Optional[dict]) -> str:
        if not result:
            return "【规则引擎】未命中任何规则，根因：未明确"
        rule = result["rule"]
        return (
            f"【规则引擎预分类】\n"
            f"  根因类别  : {rule['category']}\n"
            f"  规则名称  : {rule['name']}\n"
            f"  描述      : {rule['description']}\n"
            f"  置信度    : {result['confidence']}（命中 {result['matched_count']}/{result['total_keywords']} 个关键词）\n"
            f"  处置建议  :\n{textwrap.indent(rule['solution'], '    ')}"
        )
