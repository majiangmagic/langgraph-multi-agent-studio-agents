# PLANER.md

## 约束
- 所有编辑md文件的方式都是通过`\harness\harness_context.py`脚本去编辑json转换成md文件或者反过来使用脚本把md转换成json格式读取内容、且对于`FEATURES.md`、`DECISIONS.md`请使用索引搜索或者最新5条、绝对禁止直接读取md文件只允许脚本读取和生成到指定位置。
- 本项目架构说明见项目根目录下 `ARCHITECTURE.md`，子模块的架构设计说明见相关子模块目录的`ARCHITECTURE.md`
- 判断需要时可以读 `DECISIONS.md` 了解历史做过的重要决策和决策的原因，但不要每次都读取；
- 将会话提出的一个或者多个新功能点用`\harness\harness_context.py`脚本补充进 `FEATURES.md`，再按照优先级选取第一个优先的功能点标记为开始或者上一次会话中失败的功能点、若 `FEATURES.md`里已有一个进行中的功能点，则先只新增功能点，切记每次只做一个功能点
- 所有工作从最近一次稳定git提交开始；
- 需要时请更新Agent.md

## 每次会话要做的事情
1. 读 `PROGRESS.md` 了解当前状态；
2. 将会话提出的一个或者多个新功能点用`\harness\harness_context.py`脚本补充进 `FEATURES.md`，再按照优先级选取第一个功能点标记为开始、若  `PROGRESS.md` 里还有未完成的任务，则先只新增功能点不选择任务标记为开始，切记每次只做一个功能点
3.  回到 `PROGRESS.md` 分析是否需要更新其内容后，把功能点内的步骤分解添加进去或者不添加、如需再去`DECISIONS.md` 新增本次决策的理由。
