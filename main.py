"""
crash_analyzer/main.py

使用示例与：
    python main.py                      # 分析默认示例日志
    python main.py --batch              # 批量分析所有示例日志
    python main.py --log "你的日志文本"   # 分析自定义日志
    python main.py --file crash.log       # 从文件读取日志
    python main.py --dir /path/to/logs   # 扫描目录中的所有日志文件
    python main.py --list-models          # 列出可用模型
"""

import argparse
import json
import sys
import os
import glob

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(__file__))

from analyzer import (
    SystemPromptAnalyzer,
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


# ─────────────────────────────────────────────
#  目录扫描分析
# ─────────────────────────────────────────────
def analyze_directory(dir_path: str, model: str):
    """
    扫描目录中的所有日志文件并分析。
    支持的文件模式：
      - jbr_err*.log
      - java_error*.log
      - hs_err_pid*.log
    
    每个目录最多取2个日志文件，合并前100行后统一分析。
    
    结果格式：
    {
      "dir_name_1": {
        "files": ["file1.log", "file2.log"],
        "analysis": {...}
      },
      "dir_name_2": {
        "files": ["file3.log"],
        "analysis": {...}
      }
    }
    """
    analyzer = SystemPromptAnalyzer(model=model)

    # 查找所有匹配的日志文件
    patterns = [
        "jbr_err*.log",
        "java_error*.log",
        "hs_err_pid*.log",
    ]

    log_files = []
    for pattern in patterns:
        # 当前目录
        log_files.extend(glob.glob(os.path.join(dir_path, pattern)))
        # 递归搜索子目录
        log_files.extend(glob.glob(os.path.join(dir_path, "**", pattern), recursive=True))

    # 去重并排序
    log_files = sorted(set(log_files))

    if not log_files:
        print(f"\n⚠️  在目录 {dir_path} 中未找到匹配的日志文件")
        print(f"   支持的文件模式: {', '.join(patterns)}")
        return

    print(f"\n{'#'*60}")
    print(f"# 找到 {len(log_files)} 个日志文件")
    print(f"{'#'*60}\n")

    # 按目录分组文件
    files_by_dir = {}
    for log_file in log_files:
        # 获取相对于根目录的目录名作为键
        rel_path = os.path.relpath(os.path.dirname(log_file), dir_path)
        dir_key = rel_path if rel_path != "." else "root"
        index = dir_key.find(os.sep)
        if index != -1:
            dir_key = dir_key[:index]  # 取第一级目录作为键
        
        if dir_key not in files_by_dir:
            files_by_dir[dir_key] = []
        files_by_dir[dir_key].append(log_file)

    # 按目录分析（每个目录最多2个文件，合并后分析）
    results_by_dir = {}
    total_dirs = len(files_by_dir)
    
    for dir_idx, (dir_key, dir_files) in enumerate(files_by_dir.items(), 1):
        print(f"\n[{dir_idx}/{total_dirs}] 分析目录: {dir_key}")
        print(f"   文件数: {len(dir_files)}")
        for f in dir_files:
            print(f"     - {os.path.basename(f)}")
        print(f"{'-'*60}")

        # 找到目录中为jbr_err*.log的文件，如果有就优先分析，否则分析java_error*.log或hs_err_pid*.log
        jbr_files = [f for f in dir_files if f.endswith("jbr_err*.log")]
        if jbr_files:
            dir_files = jbr_files
        else:
            dir_files = dir_files[:1]

        try:
            # 合并所有文件的前100行
            combined_content = ""
            for log_file in dir_files:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[:100]
                    combined_content += f"\n\n=== 文件: {os.path.basename(log_file)} ===\n"
                    combined_content += "".join(lines)

            # 分析合并后的内容
            answer = json.loads(analyzer.analyze(combined_content, stream=True))

            results_by_dir[dir_key] = {
                "files": [os.path.basename(f) for f in dir_files],
                "analysis": answer,
            }
            print(f"   ✅ 分析完成")
        except Exception as e:
            print(f"   ❌ 分析失败: {e}")
            results_by_dir[dir_key] = {
                "files": [os.path.basename(f) for f in dir_files],
                "error": str(e),
            }

    # 保存结果
    output_path = os.path.join(dir_path, "analysis_results.json")
    output_list = []
    for k, v in results_by_dir.items():
        if v['analysis'] is None:
            continue
        v['analysis']['directory'] = k
        output_list.append(v['analysis'])
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_list, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 分析完成，结果已保存至 {output_path}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────
#  CLI 入口
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="IDE Crash 日志智能分析工具（基于 Ollama）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python main.py
  python main.py --batch
  python main.py --log "NullPointerException: backBuffers[i] is null"
  python main.py --file /path/to/hs_err_pid1234.log
  python main.py --dir /path/to/logs
  python main.py --list-models
        """,
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
        help="从文件读取崩溃日志（jbr_err*.log）",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="",
        help="扫描目录中的所有日志文件（jbr_err*.log, java_error*.log）",
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
                marker = " ← 当前默认" if m == DEFAULT_MODEL else ""
                print(f"  • {m}{marker}")
        except Exception as e:
            print(f"获取模型列表失败: {e}")
        return

    # 优先处理目录扫描
    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"❌ 目录不存在: {args.dir}")
            return
        analyze_directory(args.dir, args.model)
        return

    # 读取日志
    log_text = args.log
    if args.file and not log_text:
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            log_text = f.read()
        print(f"[已读取] {args.file}（{len(log_text)} 字符）")

    # 运行分析
    print(f"\n🚀 启动 Crash 分析器")
    print(f"   模型: {args.model}\n")
    run_system_prompt_mode(args.model, log_text, args.batch)


if __name__ == "__main__":
    main()
