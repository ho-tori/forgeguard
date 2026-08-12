# Agent 工作日志

> 只记录实际发生事件；不伪造 subagent、worktree、PR、commit 或 CI。

## 2026-08-12 19:xx CST — Task 0 / 要求解析

- 技能/流程：用户明确要求跳过 brainstorming；未触发该技能，记录课程流程偏离。
- Context：完整读取通用要求、Project A 要求与 `submission.jsonc`。
- 决策：选择 Coding Agent Harness，治理为重点维度；Python 标准库 + Docker；Mock LLM 离线验证。
- 人工输入：只有“阅读文档，帮我完成，不需要头脑风暴，直接做”。
- 教训：不可用生成文本冒充必需的真实流程证据、学生身份、远端 CI 或个人反思。

## 2026-08-12 19:xx CST — Task 0 / SPEC 与 PLAN

- 产出：`SPEC.md`、`PLAN.md`、`SPEC_PROCESS.md`。
- 关键约束：工作区围栏、无 shell、危险动作一次性审批、反馈完成门禁、哈希链审计、OS/secret-file 凭据。
- 验证：逐条映射课程交付清单与 A.3–A.7。
- 人工干预：无。

## 后续记录格式

每个 Task 完成后追加：真实时间、红测命令/失败摘要、绿测命令/通过摘要、触发技能、模型/context、产物或 commit hash、人工修改与原因。若项目所有者之后使用 Superpowers/subagent/worktree，应在此追加真实记录。

## 2026-08-12 19:xx CST — Task 1–7 / TDD 实现

- 红测：实现包不存在时运行 `python -m unittest discover -s tests -v`，10 个测试模块均以 `ModuleNotFoundError: forgeguard` 失败。
- 绿测：逐层实现动作解析、治理/审批、审计/记忆、工具、agent loop、凭据、Web 服务。
- 关键回归红测：超时路径被元字符策略拦截；内部状态绝对路径可绕过；失败命令错误复用旧反馈；并发审计损坏链；均先复现后修复。
- 安全修正：保护 `.git/.forgeguard/.env/私钥`；读取内容做秘密扫描；子进程清除敏感环境；任意解释器及非受限 `git status` 需审批；审计追加串行化。
- 绿测结果：最终全量 41 项通过，2 项因 Windows 缺少 POSIX 权限/可靠符号链接能力跳过。
- subagent/commit：未使用 subagent；当前目录不是 Git 仓库，无 commit hash。

## 2026-08-12 19:xx CST — Task 6 / 机制演示

- 命令：`python -m forgeguard demo`。
- 结果：确定性展示危险 Git 拦截、审批调包/重放失败、失败反馈驱动修正、审计链有效。
- LLM：仅使用 `MockLLM`，不访问网络或真实模型。

## 2026-08-12 19:xx CST — Task 8 / 分发与 Web smoke

- 源码包：生成 `dist/forgeguard-harness-0.1.0.tar.gz`；检查包含 `forgeguard/static/index.html` 与 LICENSE；从 tar 包安装到隔离目录后演示通过。
- Web：启动 `127.0.0.1:8765`，`/api/health` 返回 ok，`/api/status` 审计有效且凭据未配置，首页 200。
- Docker：客户端存在，但本机 Docker daemon 未运行，无法实际构建镜像；不可宣称构建通过。
- GitLab/部署：无项目账号或远端 URL，无法产生真实 pipeline/公网地址。
