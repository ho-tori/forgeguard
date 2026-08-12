# ForgeGuard 规格说明

版本：1.0  
状态：已批准进入实现（2026-08-12）

## 1. 问题陈述

让通用大模型直接操作代码库，会把模型的一次错误判断放大为文件破坏、凭据泄漏或错误发布。ForgeGuard 是一个面向个人开发者和课程实验的轻量 Coding Agent Harness：它自行实现 agent 主循环，在受限工作区内提供读写、命令与测试反馈工具，并把危险动作送入可审计、一次性的人工审批状态机。

目标用户是希望研究或使用 coding agent、但不愿把安全性寄托在提示词遵从上的开发者。项目价值不在于“再封装一次聊天 API”，而在于把范围围栏、动作分类、审批绑定、反馈回灌与审计完整性做成移除真实 LLM 后仍可确定性验证的代码。

### 范围

- 单 agent、单进程、一个受控工作区。
- Python 3.7+，CLI 与可访问的 WebUI。
- 真实模型通过 OpenAI-compatible Chat Completions 单次请求接入；测试使用脚本化 Mock LLM。
- 不提供自主联网浏览、任意 shell、分布式队列或多租户隔离。

## 2. 用户故事

1. 作为开发者，我希望给 agent 一个编码任务，并看到每个动作和结果，以便判断它是否沿正确方向推进。
2. 作为安全敏感用户，我希望任何越界路径都在执行前被确定性拒绝，以便模型不能读写工作区外文件。
3. 作为审批者，我希望删除、发布等危险动作暂停并生成一次性审批请求，以便审批只绑定到我实际看到的动作。
4. 作为维护者，我希望测试或 lint 失败会结构化回灌给模型，以便它可以在下一步修正，而不是假装完成。
5. 作为重复使用者，我希望项目约定和已验证事实能够跨会话保存并按任务检索，以便减少无关上下文。
6. 作为审计者，我希望发现审计日志被删除、调序或篡改，以便事后记录不是可静默改写的普通文本。
7. 作为首次使用者，我希望通过隐藏输入录入、更新、清除 API key，查看状态时不回显秘密。
8. 作为部署者，我希望用两条 Docker 命令启动 WebUI，并通过只读 secret 文件提供 key。

这些故事均可独立验收、范围可估计，并通过下文的客观测试判定。

## 3. 功能规约

### 3.1 决策与主循环

输入：任务文本、声明式配置、可选会话 ID。  
行为：构造最小上下文，调用一次 LLM，严格解析单个 JSON 动作，经过治理后分发工具，将结果与反馈追加到会话，再决定继续、等待审批、完成或失败。  
输出：最终状态、模型总结、步骤数、待审批请求或错误。  
边界：最大步数、最大模型输出、最大工具输出；格式错误作为可回灌错误，连续错误或达到上限时停止。空任务直接拒绝。

### 3.2 工具分发

工具为 `read_file`、`write_file`、`run_command`、`run_feedback`、`remember`、`finish`。输入必须通过每个工具自己的 schema 校验；未知字段和未知工具被拒绝。文件路径先解析再验证属于工作区，符号链接逃逸同样拒绝。写入采用临时文件替换，限制字节数。命令使用参数数组执行，禁止 shell 元字符和 `shell=True`。

### 3.3 客观反馈

`run_feedback` 只运行配置中的具名检查（如 `unit`），以退出码为客观信号，并返回命令、退出码、耗时、截断后的 stdout/stderr。失败结果进入下一轮上下文。`finish` 前若配置要求验证，则最近一次反馈必须通过；否则完成动作被拒绝并将原因回灌。

### 3.4 记忆

记忆存储在工作区状态目录的 SQLite 中，实体为 `Memory(id, session_id, kind, content, tags, created_at)`。`remember` 仅保存不含明显秘密的短文本；任务开始时按关键词匹配检索最多 N 条，不全量载入。用户可通过 CLI 清空记忆。

### 3.5 治理与 HITL

治理顺序：schema → 范围围栏 → 命令词法检查 → 风险规则 → 审批票据。结论为 `allow`、`deny`、`require_approval`。审批请求包含规范化动作的 SHA-256 摘要、生成时间和过期时间；批准只能消费一次，只对完全相同的动作有效。拒绝、过期、摘要不匹配均不执行。所有决定写入哈希链审计日志。

### 3.6 凭据管理

CLI 支持 `credential set/status/clear`，录入使用隐藏输入，状态不显示 key。Windows 默认写入 Credential Manager（目标名 `ForgeGuard/OpenAICompatible`）；容器和 Linux 服务从 `FORGEGUARD_API_KEY_FILE` 指向的只读文件读取。可选环境变量只作为开发兼容源，README 明确其会暴露给同用户进程、不得写入 `.env` 或提交仓库。日志、异常和 Web API 均不得记录请求中的 key。

### 3.7 WebUI

默认仅监听 `127.0.0.1:8080`，展示任务输入、运行状态、待审批动作和审计校验结果。API 提供健康检查、运行任务、批准/拒绝、凭据状态/设置/清除。非 loopback 监听必须配置 bearer 管理令牌；Web 页面不展示秘密。为避免阻塞和资源耗尽，同一时刻最多一个任务运行。

## 4. 非功能需求

- 性能：除 LLM/命令时间外，单步治理与工具分发在普通机器上低于 50 ms；日志和记忆检索有上限。
- 安全：默认最小权限、无 shell、工作区强边界、命令允许列表、危险动作代码化审批、输出截断、秘密脱敏、loopback WebUI。
- 可用性：错误返回稳定的错误码和可操作说明；CLI 退出码非零表示失败。
- 可观测性：每个决策、治理结论、工具结果和状态转换都有会话/步骤标识；JSONL 审计使用前向哈希链。
- 可靠性：原子写入；LLM 超时；命令超时后终止；Mock LLM 测试不访问网络。
- 兼容性：Python 3.7+ 标准库；Windows、Linux；容器目标 `linux/amd64` 与 `linux/arm64`（由基础镜像支持）。

### 4.1 凭据威胁模型

威胁包括：源码或 Git 历史泄漏、终端回显、进程环境读取、日志记录、浏览器页面回显、恶意工作区指令诱导 agent 读取秘密、容器层缓存。对策是：key 不进入工作区和 prompt；隐藏输入；Windows Credential Manager；Docker secret 只读挂载；状态只返回布尔值；集中脱敏；`.gitignore` 拒绝 `.env`/secret；镜像构建不接受 key 参数。已知剩余风险：同一 OS 用户、管理员、已入侵进程仍可能读取凭据；本项目不是强对抗沙箱。

## 5. 系统架构与数据流

```text
CLI / WebUI
    | task / approval / credential operation
Application service
    | context                       | status
Agent loop -> LLM adapter -> strict action parser
    | action
Policy engine -> approval store -> tool registry
                                  |-- workspace file tools
                                  |-- subprocess executor
                                  |-- feedback runner
                                  `-- memory store
    ^                                  |
    `----------- observation ----------'

Every transition -> hash-chain audit JSONL
```

外部依赖只有用户选择的 OpenAI-compatible HTTPS endpoint。生产主循环不依赖任何现成 agent 编排框架。

## 6. 数据模型

- `Action(name, arguments)`：名称与 JSON 参数；规范化后可摘要。
- `Observation(ok, code, message, data)`：稳定错误码；data 有大小上限。
- `Session(id, task, state, step, history, pending_approval)`：状态为 running/awaiting_approval/completed/failed。
- `Approval(id, action_digest, risk, status, created_at, expires_at, consumed_at)`：状态 pending/approved/rejected/expired/consumed。
- `Memory`：见 3.4；内容不得包含检测到的秘密。
- `AuditEvent(seq, timestamp, session_id, event, payload, previous_hash, hash)`：hash 覆盖除自身外的规范 JSON。

约束：ID 使用随机 UUID；时间用 UTC ISO-8601；所有持久化路径位于 `.forgeguard/`；历史与工具输出均有硬上限。

## 7. 领域与机制设计

### 工具

读/写工作区文件、运行允许列表命令、运行具名反馈、保存项目记忆、声明完成。每个工具均为自行实现的确定性分发器。

### 客观反馈信号

测试、lint 或编译命令的进程退出码。反馈 runner 生成结构化观察；主循环在下一次 LLM 调用中明确携带最近失败。Mock LLM 演示第一次写出错误、测试失败、第二次修复、测试通过。

### 危险动作

工作区逃逸和 shell 语法无条件拒绝；删除、破坏性 Git、依赖安装、网络/发布命令要求审批；未知可执行文件拒绝。规则由 `PolicyEngine` 代码和 JSON 配置共同决定，不由系统提示词决定。

### 记忆

保存用户主动要求记录的项目约定与验证事实；SQLite 检索按任务关键词筛选并限制数量。秘密扫描命中时拒绝落盘。

### 重点维度：治理

主要贡献是四层治理链：工作区规范化围栏、无 shell 的命令解析、规则化风险判定、动作摘要绑定的一次性限时审批，再用哈希链审计记录状态转换。移除 LLM 后，可直接构造动作来测试越界拒绝、危险动作暂停、篡改检测、票据过期/重放/调包失败。

## 8. 技术选型与分发

- Python 标准库：降低冷启动和供应链风险，适配课程环境 Python 3.7。
- `urllib.request`：只做供应商单次 HTTP 调用，不引入 agent SDK。
- `sqlite3`：自实现记忆检索和审批持久化所需的可靠事务。
- `http.server`：提供无依赖 WebUI；界面遵循简洁、高对比、键盘可用原则。未使用 Open Design skill，原因是本环境未安装该 skill，且 UI 只是内置控制面而非本项目主要贡献。
- Docker：主要分发形式；同时可 `pip install .`。镜像以非 root 用户运行，工作区与 secret 外部挂载。

## 9. 验收标准

1. `python -m unittest discover -s tests -v` 在无网络、无真实 key 下通过。
2. Mock 演示确定性展示危险动作等待审批、失败反馈驱动下一动作变化，以及审批票据不可重放。
3. `../`、绝对路径和工作区外符号链接均不能被读写。
4. shell 元字符不能执行；未允许命令不能执行；超时有稳定结果。
5. 未批准的危险动作不会触达工具；审批仅对原动作一次有效。
6. 修改、删除或调序一条审计记录后 `audit verify` 失败。
7. 失败反馈进入下一次 Mock LLM 上下文；未通过必需验证时不能 finish。
8. Windows 凭据设置不回显；Web/CLI status 仅显示 configured/source。
9. `docker build -t forgeguard .` 成功；容器以只读 secret file 和工作区卷启动 WebUI。
10. `.gitlab-ci.yml` 存在名为 `unit-test` 的 job，并同时运行机制演示和镜像构建检查。

## 10. 风险与未决问题

- 本项目的进程级边界不是 VM/容器强沙箱；获批命令仍继承 agent 进程权限。
- Windows Credential Manager 仅适合桌面模式；容器使用 orchestrator secret file。
- OpenAI-compatible 供应商对 JSON 输出支持不一，解析错误会被回灌但可能耗尽步数。
- WebUI 单进程设计有意限制吞吐；公开部署必须设置管理令牌并放在 TLS 反向代理后。
- 公网 URL、Git 仓库 URL、学生身份和真实 CI pass 只能由项目所有者在其账号中完成，不能在本地伪造。

