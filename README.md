# LangGraph Multi-Agent Studio Agents

本仓库保存 LangGraph Multi-Agent Workflow Studio 使用的 Agent 实现及其共址 DSL。

目录会作为主平台的 `app/agents` Git Submodule 挂载，因此 Python 包路径保持为
`app.agents.*`。生成 Agent 后，应先在本仓库提交并推送，再由主仓库更新 Submodule
指针。

场景分支：

- `scene/prompt-generation`
- `scene/supervisor-simple`

