# RUNTIME.md

## 约束
- 所有编辑md文件的方式都是通过`\harness\harness_context.py`脚本去编辑json转换成md文件或者反过来使用脚本把md转换成json格式读取内容、且对于`FEATURES.md`、`DECISIONS.md`请使用索引搜索或者最新5条、绝对禁止直接读取md文件只允许脚本读取和生成到指定位置。
- 本项目架构说明见项目根目录下 `ARCHITECTURE.md`，子模块的架构设计说明见相关子模块目录的`ARCHITECTURE.md`
- 判断需要时可以读 `DECISIONS.md` 了解历史做过的重要决策和决策的原因，但不要每次都读取；

## 每次会话要做的事情
1. 读 `PROGRESS.md` 了解未完成的内容；
2. 开发代码并实时使用脚本更新`PROGRESS.md`汇报进度，每完成里面的一小项就要去更新一次
3. 按需更新本次修改涉及的 `ARCHITECTURE.md`
