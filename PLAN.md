# ForgeGuard 实现计划

说明：每项均以失败测试开始，再写最少实现使其通过。依赖用 `→` 表示；可并行项明确标注。当前工作区不是 Git 仓库且用户要求直接实现，因此本地单工作区执行；仓库创建后由所有者按任务切分 PR。

## Task 1：领域对象与严格动作解析 ✅

- 目标：定义 Action/Observation/Session，严格解析 LLM JSON。
- 文件：`forgeguard/models.py`、`forgeguard/parser.py`、`tests/test_parser.py`
- 红测：畸形 JSON、未知动作、未知/缺失参数必须返回稳定解析错误。
- 验证：`python -m unittest tests.test_parser -v`
- 依赖：无。可与 Task 2、3 的测试设计并行。

## Task 2：治理策略与审批状态机（重点） ✅

- 目标：实现路径围栏、命令词法/风险分类、摘要绑定的一次性限时审批。
- 文件：`forgeguard/policy.py`、`forgeguard/approval.py`、`tests/test_policy.py`、`tests/test_approval.py`
- 红测：路径逃逸；shell 元字符；删除动作暂停；过期、重放、调包票据失败。
- 验证：`python -m unittest tests.test_policy tests.test_approval -v`
- 依赖：Task 1 的 Action。路径围栏与审批可并行。

## Task 3：哈希链审计与记忆 ✅

- 目标：实现追加式审计校验与 SQLite 有界检索。
- 文件：`forgeguard/audit.py`、`forgeguard/memory.py`、`tests/test_audit.py`、`tests/test_memory.py`
- 红测：篡改/删除/调序被识别；按关键词检索且秘密不落盘。
- 验证：`python -m unittest tests.test_audit tests.test_memory -v`
- 依赖：无。可与 Task 2 并行。

## Task 4：工具与客观反馈 ✅

- 目标：原子文件写入、受控 subprocess、超时/截断、具名反馈。
- 文件：`forgeguard/tools.py`、`tests/test_tools.py`
- 红测：越界读写、未知程序、元字符、超时、通过/失败退出码。
- 验证：`python -m unittest tests.test_tools -v`
- 依赖：Task 1、2。

## Task 5：LLM 抽象与 agent 主循环 ✅

- 目标：自行实现上下文→单次 LLM→动作→治理→工具→反馈→停机循环。
- 文件：`forgeguard/llm.py`、`forgeguard/agent.py`、`tests/test_agent.py`
- 红测：脚本 Mock 串行消费；危险动作在工具前暂停；失败反馈出现在下一轮；无通过反馈不能完成；步数上限停机。
- 验证：`python -m unittest tests.test_agent -v`
- 依赖：Task 1–4。

## Task 6：凭据、配置、CLI 与机制演示 ✅

- 目标：安全凭据生命周期、配置加载、命令入口、三项确定性机制演示。
- 文件：`forgeguard/credentials.py`、`forgeguard/config.py`、`forgeguard/cli.py`、`forgeguard/demo.py`、`tests/test_credentials.py`、`tests/test_config.py`
- 红测：状态不泄密、secret file 权限检查、敏感配置拒绝；演示输出稳定。
- 验证：`python -m forgeguard demo` 与相关单测。
- 依赖：Task 1–5。

## Task 7：WebUI ✅

- 目标：loopback 默认控制面、健康/状态/任务/审批/凭据 API，非本地监听鉴权。
- 文件：`forgeguard/web.py`、`forgeguard/static/index.html`、`tests/test_web.py`
- 红测：健康检查、无 token 的远端配置拒绝、凭据响应无 key、并发任务返回冲突。
- 验证：`python -m unittest tests.test_web -v`；浏览器人工检查键盘操作和窄屏。
- 依赖：Task 5、6。

## Task 8：分发、CI 与文档 ⚠️ 本地完成，外部证据待所有者账号

- 目标：Docker/pip 分发、GitLab CI、完整用户文档、安全边界和过程证据。
- 文件：`Dockerfile`、`.dockerignore`、`pyproject.toml`、`.gitlab-ci.yml`、`README.md`、`AGENT_LOG.md`、`SPEC_PROCESS.md`、`REFLECTION.md`
- 红测：CI 配置静态断言、打包元数据导入测试。
- 验证：全量单测、`python -m forgeguard demo`、`docker build -t forgeguard .`。
- 依赖：全部；文档骨架可并行。

本地完成状态：源码包已构建并从归档干净安装；GitLab CI 文件与 Dockerfile 已写。Docker daemon 在验证机器上未运行，故镜像实际构建待办；GitLab pipeline/公开部署/Release 也只能在项目所有者账号中完成。

## 完成定义

- 全量测试与机制演示通过，工作树无真实秘密。
- README 覆盖简介、安装、运行、分发、目录、安全边界、限制。
- PLAN 完成项附真实 commit hash；若尚无远端/身份，不伪造 hash、PR 或 CI 记录。

当前目录不是 Git 仓库，以上任务没有可填写的 commit hash；项目所有者初始化仓库并按真实历史提交后再补。
