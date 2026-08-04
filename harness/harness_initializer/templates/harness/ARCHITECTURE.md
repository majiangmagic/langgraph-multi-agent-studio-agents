# ARCHITECTURE.md

## 模块说明
本目录用于管理 Harness 的 ARCHITECTURE、PROGRESS、DECISIONS 和 FEATURES 四类上下文文档。

主要使用方式：
1. AI 或调用方先生成符合对应结构的 JSON。
2. 使用 harness_context.py 的 Editor 操作把 JSON 转换为固定格式 Markdown。
3. 使用 Reader 操作把 Markdown 或 JSON读取为完整 JSON。
4. DECISIONS 和 FEATURES 额外支持按日期读取最新记录以及按关键词查询。
5. 使用 check.py 分别检查四类 Markdown，或者一次执行全部检查。

首选命令格式：
python harness_context.py --operation <操作名称> --input <输入文件> --output <输出文件>

例如：
python harness_context.py --operation Features_Editor --input json_example/features.example.json --output FEATURES.md
python harness_context.py --operation Features_Reader_by_date --input FEATURES.md --output latest.json --num 5
python harness_context.py --operation Features_Reader_by_keyword --input FEATURES.md --output matches.json --keyword 购物车
python check.py <目录> --operation Features_Check
python check.py <目录>

harness_context.py 对外使用 harness_context 类，main() 通过明确的 if/elif 分支调用具体操作。check.py 对外使用 harness_check 类，并按 Progress_Check、Decisions_Check、Features_Check、Architecture_Check 和 All_Check 划分检查入口。旧版 --type 和 --direction 参数仍由 harness_context.py 兼容，但新调用优先使用 --operation。

## 目录结构
- `harness_context.py`：四类上下文文档的 JSON/Markdown 转换和查询脚本；包含格式处理器、IndexService、FileStore，以及统一公开操作类 harness_context；
- `check.py`：四类 Markdown 的检查脚本；harness_check 按文档类型提供独立检查方法，并可通过 All_Check 执行全部检查；
- `ARCHITECTURE.md`：当前目录结构、脚本职责、调用方式和设计约束说明；
- `json_example/`：存放四类上下文文档的 JSON 输入示例；
- `json_example/architecture.example.json`：生成 ARCHITECTURE.md 的 JSON 示例和当前说明数据源；
- `json_example/progress.example.json`：生成 PROGRESS.md 的 JSON 示例；
- `json_example/decisions.example.json`：生成 DECISIONS.md 的 JSON 示例；
- `json_example/features.example.json`：生成 FEATURES.md 的 JSON 示例；
- `__pycache__/`：Python 运行或语法检查自动生成的字节码缓存目录，不属于业务源文件；

## 设计约束
- 上下文 Markdown 优先由对应 JSON 通过 harness_context.py 生成，避免手工编辑破坏固定格式；
- harness_context 类按 Architecture、Progress、Decisions 和 Features 提供明确的 Editor 与 Reader 方法；
- DECISIONS 和 FEATURES 的关键词查询使用记录中的 keywords 数组；
- DECISIONS 和 FEATURES 的日期使用 YYYY-MM-DD 格式，Reader_by_date 按日期降序返回指定数量的记录；
- FEATURES.md 的规则文本由 FeaturesHandler 固定校验，JSON 中的 rules 不允许随意修改；
- check.py 按文档类型提供 Progress_Check、Decisions_Check、Features_Check 和 Architecture_Check，不通过注册器或检查流水线隐藏调用关系；
- Progress_Check 对已完成、进行中、已知问题和下一步四个区段分别限制最多 10 条，允许任一区段为 0 条；
- Decisions_Check、Features_Check 和 Architecture_Check 当前检查目标文件是否存在以及是否包含乱码；
- All_Check 只负责依次汇总四类检查结果，不修改任何 Markdown 或 JSON 文件；
- __pycache__ 是运行时缓存，可以重新生成，不应作为上下文文档或示例文件维护；
