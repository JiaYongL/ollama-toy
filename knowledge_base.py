"""
crash 诊断知识库 — 结构化规则定义
每条规则包含：匹配关键词、根因结论、建议处置措施
"""

KNOWLEDGE_RULES = [
    {
        "id": "JBR_METAL_MAC",
        "category": "JBR问题",
        "name": "Mac外接显示器导致JBR崩溃",
        "keywords": [
            "unable to initialize Metal",
            "No MTLDevice",
            "Cannot load metal library",
            "CGraphicsDevice",
        ],
        "exception_types": ["IllegalStateException"],
        "platforms": ["mac", "darwin"],
        "description": (
            "JBR在macOS上连接/断开外接显示器时，Metal图形设备重建失败，"
            "找不到MTLDevice，导致JVM崩溃。属于JBR已知问题。"
        ),
        "solution": (
            "1. 断开外接显示器后重启IDE\n"
            "2. 升级JBR到最新版本\n"
            "3. 临时规避：在IDE启动参数中添加 -Dsun.java2d.metal=false"
        ),
    },
    {
        "id": "JBR_NULL_BACK_BUFFER",
        "category": "JBR问题",
        "name": "JBR图形缓冲区空指针",
        "keywords": [
            "backBuffers[i]\" is null",
            "VolatileImage.getGraphics()",
            "backBuffers",
        ],
        "exception_types": ["NullPointerException"],
        "platforms": [],
        "description": (
            "JBR图形渲染层backBuffers数组未初始化或已被清空，属于JBR内部缺陷。"
        ),
        "solution": (
            "1. 升级JBR到最新版本\n"
            "2. 向JetBrains提交Bug报告"
        ),
    },
    {
        "id": "WIN_VIRTUAL_OOM",
        "category": "内存不足",
        "name": "Windows虚拟内存不足",
        "keywords": [
            "Native memory allocation",
            "failed to map",
            "failed to allocate",
            "G1 virtual space",
            "os_windows.cpp",
            "arena.cpp",
            "Out of Memory Error",
            "Chunk::new",
            "ChunkPool::allocate",
        ],
        "exception_types": [],
        "negative_keywords": ["Possible reasons", "physical RAM"],  # 排除物理内存不足
        "platforms": ["windows"],
        "description": (
            "Windows系统虚拟内存可用空间耗尽，JVM无法申请所需虚拟内存块。"
            "通常发生在虚拟内存剩余仅MB级别时，无法满足JVM的mmap/malloc请求。"
        ),
        "solution": (
            "1. 增加Windows虚拟内存页面文件大小（建议设为物理内存1.5~3倍）\n"
            "2. 关闭其他高内存占用程序\n"
            "3. 降低IDE堆内存设置（-Xmx参数）\n"
            "4. 升级物理内存"
        ),
    },
    {
        "id": "PHYSICAL_OOM",
        "category": "内存不足",
        "name": "物理内存不足",
        "keywords": [
            "Native memory allocation",
            "failed to allocate",
            "failed to map",
            "Possible reasons",
            "physical RAM or swap space",
            "CompressedOops",
        ],
        "exception_types": [],
        "platforms": [],
        "description": (
            "系统物理内存及Swap空间均已耗尽，JVM内存分配失败。"
            "此类报错通常出现在较新版本JBR/JVM中，会给出详细的Possible reasons提示。"
        ),
        "solution": (
            "1. 关闭其他进程释放物理内存\n"
            "2. 增加系统交换文件/Swap分区大小\n"
            "3. 升级物理内存\n"
            "4. 排查IDE内存泄漏（检查heap是否持续增长）"
        ),
    },
    {
        "id": "CHROME_ELF_VIOLATION",
        "category": "未明确",
        "name": "chrome_elf.dll兼容性访问违例",
        "keywords": [
            "EXCEPTION_ACCESS_VIOLATION",
            "chrome_elf.dll",
            "0x1b549",
            "ProcessHandleImpl.getProcessPids0",
        ],
        "exception_types": [],
        "platforms": ["windows"],
        "description": (
            "根因未明确。chrome_elf.dll（CEF/Chromium组件）与JVM进程枚举函数"
            "getProcessPids0之间存在兼容性冲突，导致访问违例。"
        ),
        "solution": (
            "1. 尝试禁用IDE中的内嵌浏览器功能（JCEF）\n"
            "2. 升级IDE及JBR版本\n"
            "3. 向JetBrains提交完整Crash日志"
        ),
    },
    {
        "id": "JBR_HARDWARE_CPU",
        "category": "JBR问题",
        "name": "JBR崩溃（疑似CPU/硬件问题）",
        "keywords": [
            "EXCEPTION_ACCESS_VIOLATION",
            "GCTaskThread",
            "GC Thread",
            "C2 CompilerThread",
            "ConcurrentGCThread",
            "data execution prevention violation",
        ],
        "exception_types": [],
        "negative_keywords": ["chrome_elf.dll", "Possible reasons"],
        "platforms": [],
        "description": (
            "JBR运行时异常，社区分析认为可能是硬件问题。"
            "常见原因：CPU/内存超频不稳定、CPU硬件故障、内存条故障、驱动未更新。"
        ),
        "solution": (
            "1. 检查BIOS中CPU/内存超频设置，恢复默认频率\n"
            "2. 运行内存稳定性测试（MemTest86）\n"
            "3. 更新主板BIOS和硬件驱动\n"
            "4. 检查杀毒软件是否拦截了JVM进程"
        ),
    },
    {
        "id": "JBR_A27_CRASH",
        "category": "JBR问题",
        "name": "JBR-A-27偶发崩溃（已知Bug）",
        "keywords": [
            "EXCEPTION_ACCESS_VIOLATION",
            "JBR-17.0.12+1-1087.25-jcef",
        ],
        "exception_types": [],
        "platforms": [],
        "description": (
            "JBR 17.0.12+1-1087.25-jcef版本中存在的已知偶发崩溃问题，"
            "已在JetBrains YouTrack记录（JBR-A-27）。"
        ),
        "solution": (
            "1. 升级JBR到更高版本（规避该版本已知Bug）\n"
            "2. 参考：https://youtrack.jetbrains.com/articles/JBR-A-27"
        ),
    },
    {
        "id": "JDK_BUG",
        "category": "JDK Bug",
        "name": "JDK已知Bug（字体渲染/类加载器）",
        "keywords": [
            "DrawGlyphListLCD",
            "EXCEPTION_IN_PAGE_ERROR",
            "0xc0000006",
            "defineClass2",
            "zip.dll",
        ],
        "exception_types": [],
        "platforms": [],
        "description": (
            "JDK已知Bug，常见于字体渲染（DrawGlyphListLCD）"
            "或类加载器（defineClass2）的底层缺陷。"
        ),
        "solution": (
            "1. 升级JDK/JBR到修复该Bug的版本\n"
            "2. 向JetBrains或OpenJDK社区提交Bug报告"
        ),
    },
]

# 用于System Prompt的精简知识文本
SYSTEM_KNOWLEDGE_TEXT = """
你是一个专业的IDE崩溃日志分析专家，专注于JetBrains系列IDE和DevEco Studio的崩溃诊断。

## 诊断规则库

### 规则1：Mac外接显示器JBR崩溃
- 触发条件：出现 `IllegalStateException` + `No MTLDevice` + `Cannot load metal library`
- 根因：JBR在macOS上Metal图形设备重建失败
- 结论标签：JBR问题，mac上外接显示器导致JBR崩溃

### 规则2：JBR空指针（backBuffers）
- 触发条件：`NullPointerException` + `backBuffers[i] is null` + `VolatileImage.getGraphics()`
- 根因：JBR图形缓冲区未初始化
- 结论标签：JBR问题，空指针

### 规则3：Windows虚拟内存不足
- 触发条件：`Native memory allocation` + `failed to map/allocate` + `os_windows.cpp` 或 `arena.cpp`，且【无】`Possible reasons`提示段落
- 根因：Windows虚拟内存可用空间耗尽（通常剩余<50MB）
- 结论标签：虚拟内存不足

### 规则4：物理内存不足
- 触发条件：`Native memory allocation failed` + `# Possible reasons:` + `physical RAM or swap space`
- 根因：物理内存及Swap空间均耗尽
- 结论标签：物理内存不足，内存分配失败导致crash

### 规则5：chrome_elf.dll访问违例
- 触发条件：`EXCEPTION_ACCESS_VIOLATION` + `chrome_elf.dll+0x1b549` + `ProcessHandleImpl.getProcessPids0`
- 根因：CEF组件与JVM进程枚举兼容性问题
- 结论标签：未明确

### 规则6：JBR硬件问题（CPU）
- 触发条件：`EXCEPTION_ACCESS_VIOLATION` + `jvm.dll` + 线程为`GCTaskThread`/`GC Thread#N`/`C2 CompilerThread`
- 根因：JBR崩溃，社区分析为CPU/硬件不稳定
- 结论标签：JBR问题，社区分析可能是硬件问题（CPU）

### 规则7：JBR-A-27偶发崩溃
- 触发条件：`EXCEPTION_ACCESS_VIOLATION` + `JBR-17.0.12+1-1087.25-jcef`
- 根因：JBR特定版本已知Bug（YouTrack JBR-A-27）
- 结论标签：JBR已知偶发崩溃，参考JBR-A-27

### 规则8：JDK已知Bug
- 触发条件：`DrawGlyphListLCD` 或 `EXCEPTION_IN_PAGE_ERROR` + `defineClass2`/`zip.dll`
- 根因：JDK底层字体渲染或类加载器缺陷
- 结论标签：JDK Bug

### 关键区分规则
- 虚拟内存不足 vs 物理内存不足：看是否有 `# Possible reasons: The system is out of physical RAM` 这一行，有则为物理内存不足，无则为虚拟内存不足
- 硬件问题 vs JBR-A-27：看JBR版本号，`JBR-17.0.12+1-1087.25-jcef` 特定版本优先匹配JBR-A-27

## 输出格式要求（重要）

**你只能输出纯 JSON 格式，不要输出任何其他文字、解释或 markdown 标记。**

输出字段包括：
1. root_cause：从以上规则中匹配得到的根因结论标签
2. key_info：从日志中摘录支撑结论的关键片段（1-5行，数组格式）
3. confidence：高/中/低
4. unknown_reason：说明无法确定的原因（空字符串如果已确定）

输出示例（严格遵循此格式）：
```json
{
    "root_cause": "Windows虚拟内存不足",
    "key_info": [
        "Native memory allocation (mmap) failed to map 2097152 bytes for committing reserved memory.",
        "OS error: 0x00000008, Not enough storage is available to process this command.",
        "Failed to commit virtual memory."
    ],
    "confidence": "高",
    "unknown_reason": ""
}
```

如果日志不匹配任何规则，root_cause为「未明确」并在unknown_reason中说明原因。

**再次强调：只输出JSON，不要有任何其他文字！**
"""
