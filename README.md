# ForgeGuard

ForgeGuard 是一个自行实现主循环的 Coding Agent Harness。它把真实 LLM 限定为“决定下一步动作”的组件，其余部分——严格动作解析、工具分发、工作区围栏、危险动作审批、测试反馈回灌、记忆、停机和审计——均由仓库中的 Python 代码实现，并可在 Mock LLM 下离线测试。

主贡献是代码化治理，而不是一条“请勿执行危险命令”的提示词：危险动作会在工具执行前暂停，审批票据绑定规范化动作摘要、限时且只能消费一次；审计记录形成可验证的哈希链。

## 快速体验

无需 API key 或网络即可运行确定性机制演示：

```bash
python -m forgeguard demo
```

输出依次证明：

1. `git reset --hard` 被护栏暂停；
2. 审批不能被调包或重放；
3. 一次失败测试被回灌，Mock LLM 改变动作并修正文件；
4. 审计哈希链有效。

运行全部测试：

```bash
python -m unittest discover -s tests -v
```

支持 Python 3.7+，测试不访问网络，也不需要真实凭据。

## 只判断策略，不执行动作

`policy-check` 严格解析一个 Action JSON，并只返回现有 `PolicyEngine` 的治理判断。它不会执行文件写入、命令或反馈检查，不会创建或消费 approval，也不会初始化审计、记忆、凭据、LLM 或网络客户端。

通过参数传入：

```powershell
python -m forgeguard --workspace . policy-check --action-json '{"action":"run_command","arguments":{"argv":["git","status","--short"]}}'
```

或通过重定向 stdin 传入：

```powershell
'{"action":"read_file","arguments":{"path":"README.md"}}' | python -m forgeguard --workspace . policy-check
```

成功解析的 stdout 固定包含 `verdict`、`reason` 和 `risk`：

```json
{"reason": "Constrained git status is read-only", "risk": null, "verdict": "allow"}
```

退出码：`0=allow`、`2=require_approval`、`3=deny`、`4=输入、Action 解析或配置错误`。错误也只在 stdout 输出 JSON，stderr 为空。命令读取全局 `--workspace`，并读取 `--config` 中的状态目录和命令白名单设置，但不需要 API key、LLM 或网络。

确定性机制演示的 `5_policy_check` 事件使用一个若执行就会创建文件的 Python Action，并证明结果为 `require_approval` 且文件未创建：

```powershell
python -m forgeguard demo
```

## 安装

### 源码运行

```bash
python -m pip install --no-deps .
forgeguard demo
```

项目无第三方运行时依赖。建议在虚拟环境内安装。

### Docker 分发

构建镜像：

```bash
docker build -t forgeguard:local .
```

在 Linux/macOS 上准备两个不进入仓库的只读 secret 文件：

```bash
mkdir -p "$HOME/.config/forgeguard"
umask 077
printf '%s' 'YOUR_PROVIDER_KEY' > "$HOME/.config/forgeguard/api-key"
python -c "import secrets; print(secrets.token_urlsafe(32))" > "$HOME/.config/forgeguard/admin-token"
chmod 600 "$HOME/.config/forgeguard/api-key" "$HOME/.config/forgeguard/admin-token"
```

启动 WebUI：

```bash
docker run --rm -p 127.0.0.1:8080:8080 \
  --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD",dst=/workspace \
  --mount type=bind,src="$HOME/.config/forgeguard/api-key",dst=/run/secrets/forgeguard_api_key,readonly \
  --mount type=bind,src="$HOME/.config/forgeguard/admin-token",dst=/run/secrets/forgeguard_admin_token,readonly \
  forgeguard:local
```

打开 `http://127.0.0.1:8080`，将 admin-token 文件内容输入“远程管理令牌”。API key 不会进入镜像层或构建参数。

`--user` 让 agent 以宿主当前用户的 UID/GID 修改挂载的代码库；不传时镜像仍默认以 UID 10001 的非 root 用户运行，但宿主工作区可能不可写。

已知分发限制：镜像基于官方 Python slim 镜像，目标架构随所用基础镜像而定，未签名；容器仅提供进程/用户级隔离，不是用于运行不可信恶意代码的强沙箱。Windows Docker Desktop 的 bind mount 权限语义可能无法满足 `0600` 检查，生产环境建议使用 Linux 主机或编排平台 secret。

## 安全配置 API key

### Windows 桌面

隐藏输入并保存到当前用户的 Windows Credential Manager：

```powershell
forgeguard credential set
forgeguard credential status
forgeguard credential clear
```

`status` 只返回 `configured` 和来源，不回显 key。凭据目标名为 `ForgeGuard/OpenAICompatible`。

### Linux/容器

ForgeGuard 从 `FORGEGUARD_API_KEY_FILE` 指向的文件读取，POSIX 权限必须为 `0600` 或更严格。服务不会在启动时把 secret 复制到工作区。

兼容模式 `FORGEGUARD_API_KEY` 环境变量也可读取，但不推荐：同一用户的其它进程、崩溃转储和诊断工具可能看到进程环境。不要在仓库创建 `.env`；`.gitignore` 和 `.dockerignore` 已排除常见秘密文件，但这不能替代提交前审查。

## 配置与运行

复制 `config.example.json` 到工作区外或改名为 `forgeguard.json`。配置文件禁止出现 `api_key`、`token`、`secret` 等字段；这类字段会导致启动失败。

主要配置：

- `endpoint` / `model`：OpenAI-compatible Chat Completions 单次 HTTP endpoint 与模型名；
- `allowed_commands`：模型可请求的可执行文件范围；
- `feedback_checks`：由所有者定义的具名、可信 argv 数组；
- `require_feedback`：为 true 时，最近文件/命令变更后必须有成功反馈才能 finish；
- `max_steps` / `command_timeout`：资源上限；
- `bind` / `port`：Web 监听地址。

运行单个任务：

```bash
forgeguard --workspace /path/to/repo --config /safe/path/forgeguard.json run "修复失败测试，并在完成前运行 unit 检查"
```

启动本机 WebUI：

```bash
forgeguard --workspace /path/to/repo --config /safe/path/forgeguard.json serve
```

默认监听 `127.0.0.1:8080`。绑定 `0.0.0.0` 时必须额外传入至少 16 字符、权限为 `0600` 的管理令牌文件：

```bash
forgeguard --workspace /path/to/repo --config forgeguard.json serve \
  --bind 0.0.0.0 --admin-token-file /run/secrets/forgeguard_admin_token
```

公开部署必须置于 TLS 反向代理后，并限制来源网络。`/api/health` 无需鉴权；其它 API 在配置管理令牌后要求 bearer token。

## WebUI 接口

控制面提供：

- 输入任务并查看最终状态；
- 查看凭据是否配置、审计链是否有效；
- 查看危险动作的完整参数与风险类别，并进行一次性批准或拒绝；
- 安全设置/清除桌面凭据。

同一服务只允许一个活动任务；出现待审批时不能启动新任务。

## 目录结构

```text
forgeguard/
  agent.py          自行实现的 agent 主循环与完成门禁
  parser.py         严格 JSON 动作解析
  policy.py         工作区、命令与风险治理
  approval.py       动作摘要绑定的审批状态机
  tools.py          文件、进程、反馈与记忆工具
  llm.py            Mock 与单次真实 LLM 抽象
  memory.py         SQLite 有界记忆与秘密检测
  audit.py          哈希链审计及校验
  credentials.py    Credential Manager / secret file
  service.py        单任务应用服务
  web.py + static/  Web API 与控制面
tests/              无网络的 Mock LLM 确定性测试
SPEC.md             产品、架构、安全与验收规格
PLAN.md             TDD 实现任务
SPEC_PROCESS.md     真实过程与待补冷启动证据
AGENT_LOG.md        agent 协作日志
```

## 安全边界

已编码的保证：

- 文件路径经规范化后必须处于工作区；工作区外符号链接目标也被拒绝；
- `.forgeguard/`、`.git/` 以及常见凭据文件受保护；
- 命令以 argv 和 `shell=False` 执行，拒绝 shell 元字符和未知可执行文件；
- 仅受限 `git status` 可免批执行；任意 Python、非只读 Git、安装和发布类动作需人工审批；
- 子进程环境会移除名称疑似 key/token/secret/password/credential/authorization 的变量；
- 工具输出、文件和步骤数均有限制；测试退出码作为客观反馈；
- API key 不进入 prompt、审计 payload 或状态响应；
- 审批限时、一次性且绑定完整动作摘要；审计支持篡改与截断检测。

明确不保证：

- 这不是 OS/VM 级强沙箱。用户批准任意代码后，该代码仍以 ForgeGuard 进程用户权限运行；在 Windows 下，同用户进程理论上可访问该用户的 Credential Manager。
- 模型可能产生错误动作；harness 通过拒绝、反馈和上限控制影响，但不保证任务结果正确。
- 哈希链能发现事后修改，不是带外远程见证；同时删除日志和 head 文件会表现为新日志。生产环境应把 head/hash 发送到外部只写存储。
- 管理 token 本身需由部署平台安全保存；内置 HTTP 服务不终结 TLS。

本机无 token 模式还会校验浏览器 `Host` 为 loopback，降低 DNS rebinding 风险；远程模式必须使用 bearer 管理令牌。

## 审计与维护

```bash
forgeguard --workspace /path/to/repo audit-verify
forgeguard --workspace /path/to/repo memory-clear
```

`.forgeguard/` 保存审计、审批和记忆数据库，已从 Git 与镜像上下文排除。备份或删除前停止服务。

## CI/CD

`.gitlab-ci.yml` 包含课程要求的 `unit-test` job，同时执行 Mock 机制演示；`package-smoke` 验证安装包入口；`docker-build` 构建镜像。推送后应在 GitLab 确认最后一次 pipeline 全部通过，并把真实记录/链接补入课程材料。

本地等价验证：

```bash
python -m unittest discover -s tests -v
python -m forgeguard demo
docker build -t forgeguard:local .
```

## 课程交付状态

本地工程文件已提供，但以下内容必须由项目所有者用真实账号/个人经历完成，仓库不会伪造：

- 修改 `submission.jsonc` 中的学号、姓名、仓库和部署/Release URL；
- 初始化 Git 仓库，按 `PLAN.md` 拆分真实 commit/worktree/PR，并补 commit hash；
- 安装并实际执行课程指定的 Superpowers 工作流，在 `AGENT_LOG.md` 中追加证据；
- 使用另一种全新 agent 仅凭 SPEC/PLAN 做冷启动，把真实问题和修订 diff 写入 `SPEC_PROCESS.md`；
- 学生本人完成 1500–2500 字 `REFLECTION.md`；
- 推送 GitLab，确认最后 pipeline pass；部署 WebUI，并填写截止前可访问 URL。

## 第三方代码与许可证

运行时代码仅使用 Python 标准库，没有复制第三方实现。Docker 基础镜像和构建工具分别受其自身许可证约束。本仓库代码采用 [MIT License](LICENSE)。
