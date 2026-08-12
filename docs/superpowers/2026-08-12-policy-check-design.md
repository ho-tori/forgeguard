# policy-check 设计规格

日期：2026-08-12
状态：已批准，暂不实现

## 1. 背景与目标

ForgeGuard 已通过严格 Action 解析、工作区围栏、命令词法检查和规则化风险判断实现代码化治理，但目前只能在 agent 主循环和工具分发路径中使用这些能力。

本增量功能新增 CLI 子命令 `policy-check`。用户提交一个 Action JSON 后，命令只运行严格解析和 `PolicyEngine` 判断，输出 `allow`、`deny` 或 `require_approval`，绝不执行该 Action。该命令不需要 API key、LLM 或网络，适合脚本、CI 和人工检查使用。

## 2. 已批准的用户契约

### 2.1 输入

命令支持两种互斥输入来源：

- `--action-json`：直接传入完整 Action JSON 字符串；
- stdin：未传 `--action-json` 时，从标准输入读取完整 Action JSON。

若同时传入 `--action-json` 且已重定向的 stdin 中存在非空内容，则返回输入错误。空输入同样返回输入错误。CLI 只读取已重定向的 stdin；交互式终端 stdin 视为未提供，不能为了探测冲突而阻塞等待输入。

Action 必须通过现有 `parse_action()` 的严格 schema。允许检查的 Action 与现有解析器完全一致：

- `read_file`
- `write_file`
- `run_command`
- `run_feedback`
- `remember`
- `finish`

不为 `policy-check` 维护第二套 Action schema。

### 2.2 成功判断输出

合法 Action 的 stdout 只输出一个 JSON 对象，固定包含三个字段：

```json
{"verdict":"allow","reason":"Path is inside the configured workspace","risk":null}
```

- `verdict`：`allow`、`deny` 或 `require_approval`；
- `reason`：策略判断原因；
- `risk`：风险分类；无分类时为 JSON `null`。

输出不包含输入 Action、规范化 Action 或 Action 摘要。

### 2.3 退出码

| 退出码 | 含义 |
|---:|---|
| `0` | `allow` |
| `2` | `require_approval` |
| `3` | `deny` |
| `4` | 输入、Action 解析或配置错误 |

### 2.4 错误输出

输入、Action 解析或配置错误在 stdout 输出稳定 JSON，stderr 保持为空。例如：

```json
{"error":"invalid_action","message":"Top-level object must contain only action and arguments"}
```

错误对象固定包含 `error` 和 `message`。所有此类错误退出码均为 `4`。稳定错误类别为：

- `invalid_input`：输入为空或同时使用两种输入来源；
- `invalid_action`：JSON 或 Action schema 无效；
- `invalid_config`：配置文件无法读取或不合法。

## 3. 架构与数据流

采用已批准的方案 A：“纯服务函数 + 薄 CLI 适配层”。

新增无副作用模块 `forgeguard/policy_check.py`。其核心函数接收原始 Action JSON 和已构造的 `PolicyEngine`，只执行：

```text
原始 Action JSON
    -> parse_action()
    -> PolicyEngine.evaluate()
    -> 固定 policy-check 结果
```

CLI 的 `policy-check` 分支负责：

1. 从 `--action-json` 或 stdin 取得唯一输入；
2. 调用现有 `load_config()`；
3. 使用 `config.workspace`、`config.allowed_commands` 和 `config.state_dir` 构造与真实服务一致的 `PolicyEngine`；
4. 调用纯服务函数；
5. 对输出做最终脱敏；
6. 序列化 JSON，并映射退出码。

核心函数不负责 argparse、stdin、配置文件读取、打印或进程退出码。

## 4. 安全与副作用边界

`policy-check` 路径不得构造或调用：

- `ForgeGuardService`
- `CredentialManager`
- `ApprovalStore`
- `AuditLog`
- `MemoryStore`
- `ToolRegistry`
- 任何 LLM adapter
- 网络客户端或 subprocess

因此：

- `allow` 仅表示策略允许，不执行 Action；
- `deny` 仅返回拒绝原因；
- `require_approval` 仅表示风险判断，不创建、批准或消费 approval；
- 不创建 `.forgeguard` 目录或数据库；
- 不写入审计日志、记忆或工作区文件；
- 不启动命令、反馈检查、服务或网络请求；
- 不读取或要求 API key。

命令仍读取用户明确指定的配置文件，因为 `allowed_commands`、工作区和自定义状态目录会影响真实策略结果。除此之外不初始化运行时服务。

## 5. 配置一致性

`policy-check` 复用现有全局 `--workspace` 和 `--config` 参数。它调用 `load_config()` 取得规范化后的 `workspace`、`allowed_commands` 和 `state_dir`，并按真实 service 的方式构造策略：

```text
PolicyEngine(
    config.workspace,
    config.allowed_commands,
    protected_paths=[config.state_dir],
)
```

这确保对自定义状态目录、命令白名单和工作区边界的判断不会漂移。配置中的 endpoint、model 和 feedback checks 可以被正常校验，但不会触发 LLM、工具或反馈执行。

## 6. 秘密处理

疑似 API key、token、密码、Authorization 值或私钥片段不改变治理判定本身。命令完成严格解析与策略判断，但不能把秘密带到输出。

- 不回显原始 Action 或 arguments；
- 对成功与错误消息执行现有集中脱敏；
- `reason`、`risk`、`error` 和 `message` 在序列化前都经过安全处理；
- stdout 与 stderr 均不得包含原始秘密；
- 测试对 stdout、stderr 及返回对象表示执行泄漏断言。

复用现有 `redact_secrets()`，不新增第二套秘密正则。

## 7. 错误处理与确定性

错误在 CLI 边界转换为固定 JSON 和退出码 `4`。核心策略函数不捕获不相关的编程错误，以免掩盖缺陷。

输出使用确定性 JSON 序列化：字段集合固定，不包含时间戳、UUID、文件内容或环境秘密。同一 workspace、config 和 Action 必须产生相同 verdict、reason、risk 与退出码。

仅当 stdin 不是交互式终端时才读取；读取后只把非空内容视为已提供输入，避免空管道与 `--action-json` 产生虚假冲突。未传 `--action-json` 且 stdin 为交互式终端时，立即返回 `invalid_input`，不进入交互等待模式。

## 8. 测试设计

所有测试均不访问网络、不使用真实凭据，并在临时工作区中确定性运行。

### 8.1 纯服务函数测试

- 合法 `read_file` 返回 `allow`、原因和 `risk=null`；
- 越界路径返回 `deny` 和 `workspace_escape`；
- `git reset --hard` 返回 `require_approval` 和 `destructive_git`；
- 六种现有 Action schema 均可进入策略判断；
- 非法 JSON、额外字段、未知 Action 和错误参数类型被严格拒绝；
- 输入含疑似秘密时，结果表示中不出现原始秘密。

### 8.2 CLI 契约测试

- `--action-json` 与 stdin 分别可用；
- 两种非空输入同时存在或输入为空时输出 `invalid_input`，退出 `4`；
- 三种 verdict 分别映射退出码 `0`、`2`、`3`；
- Action 解析错误与配置错误映射到退出码 `4`；
- 成功响应固定包含 `verdict`、`reason`、`risk`；
- 错误响应固定包含 `error`、`message`；
- 所有 policy-check 情形 stderr 为空，stdout 是单个可解析 JSON 对象；
- 自定义 `allowed_commands`、workspace 和 state directory 与真实 service 的策略一致。

### 8.3 无副作用证明

- 调用前后临时工作区目录树保持不变；
- `require_approval` 不创建 approval 数据库或 `.forgeguard`；
- 替身令 `ToolRegistry`、service、LLM、subprocess、凭据和审批构造器在被调用时立即失败，以证明 policy-check 路径不会触达它们；
- Action 请求写文件或运行命令时，只返回治理结论，目标文件不存在且命令副作用未发生。

### 8.4 回归验证

- policy-check 专项单元测试；
- 全量 `unittest`；
- 现有 Mock LLM demo；
- Python `compileall`；
- `git diff --check`；
- 凭据与示例占位符扫描。

## 9. 文档变更范围

实现阶段更新 README，加入 `--action-json` 与 stdin 示例、三种 verdict、退出码、错误契约，以及“只判断、不执行、不创建 approval”和“不依赖 API key、LLM 或网络”的保证。

本增量功能的真实过程记录保存在 `SPEC_PROCESS.md`，并明确区分于原始项目开发过程。

## 10. 非目标

本次不实现：

- 执行已允许的 Action；
- 创建、列出、批准或消费 approval；
- 批量检查多个 Action；
- Web API 或 WebUI policy-check；
- 从文件路径读取 Action JSON；
- 修改现有策略规则或 Action schema；
- 在线策略服务、LLM 辅助解释或网络访问；
- 审计记录或持久化检查历史。

## 11. 批准记录

2026-08-12，项目所有者在完成七轮真实需求问答并选择方案 A 后明确批准本设计，要求保存设计文档但暂时不要实现。
