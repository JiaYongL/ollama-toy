"""
crash_analyzer/main.py

使用示例与演示入口。
运行方式：
    python main.py --mode system          # System Prompt 直注法
    python main.py --mode rag             # RAG 检索增强法
    python main.py --mode rule            # 纯规则引擎（无LLM，极速）
    python main.py --mode system --batch  # 批量分析
    python main.py --log "你的日志文本"   # 分析自定义日志
    python main.py --file crash.log       # 从文件读取日志
"""

import argparse
import json
import sys
import os

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(__file__))

from analyzer import (
    SystemPromptAnalyzer,
    RAGAnalyzer,
    RuleEnginePreFilter,
    list_models,
    DEFAULT_MODEL,
)


# ─────────────────────────────────────────────
#  示例崩溃日志（覆盖所有根因类型）
# ─────────────────────────────────────────────
DEMO_LOGS = [
    # Case 1: Mac JBR Metal 崩溃
    """java.lang.IllegalStateException: Error - unable to initialize Metal after recreation of graphics device. Cannot load metal library: No MTLDevice.
java.desktop/sun.awt.CGraphicsDevice.<init>(CGraphicsDevice.java:91)
Exception in NSApplicationAWT: java.lang.IllegalStateException: Error - unable to initialize Metal""",

    # Case 2: Windows 虚拟内存不足
    """Native memory allocation (malloc) failed to allocate 1407664 bytes. Error detail: Chunk::new
Out of Memory Error (arena.cpp:191), pid=2680, tid=9240
# There is insufficient memory for the Java Runtime Environment to continue.""",

    # Case 3: 物理内存不足（有 Possible reasons 段）
    """# Native memory allocation (malloc) failed to allocate 1330048 bytes. Error detail: Chunk::new
# Possible reasons:
#   The system is out of physical RAM or swap space
#   This process is running with CompressedOops enabled, and the Java Heap may be blocking the growth of the native heap""",

    # Case 4: chrome_elf.dll 访问违例
    """EXCEPTION_ACCESS_VIOLATION (0xc0000005) at pc=0x0000000000000000, pid=928, tid=5776
# Problematic frame:
# C  [chrome_elf.dll+0x1b549]  java.lang.ProcessHandleImpl.getProcessPids0""",

    # Case 5: GC 线程崩溃（疑似硬件问题）
    """EXCEPTION_ACCESS_VIOLATION (0xc0000005) at pc=0x00007ffd4c6c2580, pid=33548, tid=4488
# Problematic frame:
# V  [jvm.dll+0x3f6d67]
Current thread (0x000002617bfc3730): GCTaskThread "GC Thread#5" [stack: 0x000000777e600000,0x000000777e700000] [id=22192]""",

    # Case 6: JBR-A-27 偶发崩溃
    """# EXCEPTION_ACCESS_VIOLATION (0xc0000005) at pc=0x00007ffcaed3c475, pid=17708, tid=5556
# JRE version: OpenJDK Runtime Environment JBR-17.0.12+1-1087.25-jcef (17.0.12+1) (build 17.0.12+1-b1087.25)
# Java VM: OpenJDK 64-Bit Server VM JBR-17.0.12+1-1087.25-jcef
# Problematic frame:
# V  [jvm.dll+0x36c475]""",

    # Case 7: JBR 空指针
    """java.lang.NullPointerException: Cannot invoke "java.awt.image.VolatileImage.getGraphics()" because "this.backBuffers[i]" is null""",
]


# ─────────────────────────────────────────────
#  运行演示
# ─────────────────────────────────────────────
def run_system_prompt_mode(model: str, log: str, batch: bool):
    analyzer = SystemPromptAnalyzer(model=model)

    if batch:
        print(f"\n{'#'*60}")
        print(f"# 批量分析模式（共 {len(DEMO_LOGS)} 条日志）")
        print(f"{'#'*60}\n")
        results = analyzer.batch_analyze(DEMO_LOGS)
        output_path = "batch_results.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 批量分析完成，结果已保存至 {output_path}")
    else:
        target_log = log if log else DEMO_LOGS[2]  # 默认展示物理内存不足
        analyzer.analyze(target_log)


def run_rag_mode(model: str, log: str):
    analyzer = RAGAnalyzer(chat_model=model)
    target_log = log if log else DEMO_LOGS[1]  # 默认展示虚拟内存不足
    result = analyzer.analyze_with_scores(target_log)
    print("\n[RAG 检索分数]")
    for r in result["retrieved_rules"]:
        print(f"  {r['name']}: {r['score']:.4f}")


def run_rule_engine_mode(log: str):
    """纯规则引擎模式，无需LLM，毫秒级响应"""
    engine = RuleEnginePreFilter()
    print(f"\n{'='*60}")
    print("规则引擎预分类（无LLM，基于关键词匹配）")
    print(f"{'='*60}")

    logs_to_check = [log] if log else DEMO_LOGS
    for i, crash_log in enumerate(logs_to_check, 1):
        preview = crash_log[:100].replace("\n", " ")
        print(f"\n[日志 {i}] {preview}...")
        result = engine.prefilter(crash_log)
        print(engine.format_result(result))
        print("-" * 40)


def run_hybrid_mode(model: str, log: str):
    """
    混合模式：规则引擎快速预判 + LLM 深度分析
    若规则引擎置信度为高，直接返回；否则调用LLM补充分析
    """
    engine = RuleEnginePreFilter()
    target_log = log if log else DEMO_LOGS[0]

    print("\n[混合模式] 第一步：规则引擎快速预判")
    result = engine.prefilter(target_log)
    print(engine.format_result(result))

    if result and result["confidence"] == "高":
        print("\n[混合模式] 规则引擎置信度高，跳过LLM调用 ✓")
    else:
        print("\n[混合模式] 规则引擎置信度不足，调用LLM深度分析...")
        analyzer = SystemPromptAnalyzer(model=model)
        analyzer.analyze(target_log)


# ─────────────────────────────────────────────
#  CLI 入口
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="IDE Crash 日志智能分析工具（基于 Ollama）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python main.py --mode system
  python main.py --mode rag
  python main.py --mode rule
  python main.py --mode hybrid
  python main.py --mode system --batch
  python main.py --mode system --log "NullPointerException: backBuffers[i] is null"
  python main.py --mode system --file /path/to/hs_err_pid1234.log
  python main.py --list-models
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["system", "rag", "rule", "hybrid"],
        default="system",
        help="知识注入模式（默认: system）",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama 模型名（默认: {DEFAULT_MODEL}）",
    )
    parser.add_argument(
        "--log",
        type=str,
        default="",
        help="直接传入崩溃日志文本",
    )
    parser.add_argument(
        "--file",
        type=str,
        default="",
        help="从文件读取崩溃日志（hs_err_pid*.log）",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="批量分析所有内置示例日志",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="列出本地所有可用 Ollama 模型",
    )

    args = parser.parse_args()

    # 列出模型
    if args.list_models:
        try:
            models = list_models()
            print("本地可用模型：")
            for m in models:
                marker = " ← 当前默认" if m.startswith(DEFAULT_MODEL) else ""
                print(f"  • {m}{marker}")
        except Exception as e:
            print(f"获取模型列表失败: {e}")
        return

    # 读取日志
    log_text = args.log
    if args.file and not log_text:
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            log_text = f.read()
        print(f"[已读取] {args.file}（{len(log_text)} 字符）")

    # 分发到对应模式
    print(f"\n🚀 启动 Crash 分析器")
    print(f"   模式: {args.mode}")
    print(f"   模型: {args.model}\n")

    if args.mode == "system":
        run_system_prompt_mode(args.model, log_text, args.batch)
    elif args.mode == "rag":
        run_rag_mode(args.model, log_text)
    elif args.mode == "rule":
        run_rule_engine_mode(log_text)
    elif args.mode == "hybrid":
        run_hybrid_mode(args.model, log_text)


if __name__ == "__main__":
    main()
