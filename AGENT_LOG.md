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

## 2026-08-13T00:17:06.0594295+08:00 — policy-check

- Worktree/baseline：工作树为 `E:\project\.worktrees\feat\policy-check`，分支 `feat/policy-check`，基线 `4c8976b`；基线命令 `python -m unittest discover -s tests -v` exit `0`，运行 41 tests、0 failures、2 个既有 Windows skips。
- Implementers：Task 1 `/root/task1_implementer`；Task 2 `/root/task2_implementer`；Task 3 `/root/task3_implementer`；Task 4 `/root/task4_implementer`；Task 5 `/root/task5_implementer`。
- RED/GREEN/REFACTOR — Task 1：RED `python -m unittest tests.test_policy_check -v` 因缺少 `forgeguard.policy_check`，1 个 discovery error；GREEN 同命令 3/3；REFACTOR `python -m unittest tests.test_policy_check tests.test_parser tests.test_policy -v` 为 15 tests、1 个既有 Windows symlink skip，compileall exit `0`。
- RED/GREEN/REFACTOR — Task 2 初始轮：RED/GREEN command 均为 `python -m unittest tests.test_cli_policy_check -v`；RED 因未注册 `policy-check`，6 tests 中出现 10 个 argparse errors，GREEN 6/6。实际 REFACTOR command 为 `python -m unittest tests.test_cli_policy_check tests.test_config tests.test_credentials tests.test_web -v`，15 tests、1 个既有 Windows skip；另运行 `python -m compileall -q forgeguard/cli.py tests/test_cli_policy_check.py` 与 `git diff --check -- forgeguard/cli.py tests/test_cli_policy_check.py`，均 exit `0`。
- RED/GREEN/REFACTOR — Task 2 修复轮 1：focused RED/GREEN command 均为 `python -m unittest tests.test_cli_policy_check.CliPolicyCheckTests.test_non_hashable_action_name_is_invalid_action_json tests.test_cli_policy_check.CliPolicyCheckTests.test_config_type_errors_are_invalid_config_json -v`；RED 为 2 tests、3 个 TypeErrors，GREEN 2/2。随后 `python -m unittest tests.test_cli_policy_check -v` 为 8/8；REFACTOR `python -m unittest tests.test_cli_policy_check tests.test_config tests.test_credentials tests.test_web -v` 为 17 tests、1 个既有 Windows skip；另运行 `python -m compileall -q forgeguard/cli.py tests/test_cli_policy_check.py` 与 `git diff --check -- forgeguard/cli.py tests/test_cli_policy_check.py`，均 exit `0`。
- RED/GREEN/REFACTOR — Task 2 修复轮 2：focused RED/GREEN command 均为 `python -m unittest tests.test_cli_policy_check.CliPolicyCheckTests.test_allowed_command_shape_errors_are_invalid_config_json -v`；RED 为 1 test，观察到 1 个 `invalid_action`/`invalid_config` failure 和 1 个 `AttributeError`，GREEN 1/1。边界回归 command 为 `python -m unittest tests.test_cli_policy_check.CliPolicyCheckTests.test_allowed_command_shape_errors_are_invalid_config_json tests.test_cli_policy_check.CliPolicyCheckTests.test_non_hashable_action_name_is_invalid_action_json tests.test_cli_policy_check.CliPolicyCheckTests.test_config_type_errors_are_invalid_config_json -v`，3/3；`python -m unittest tests.test_cli_policy_check -v` 为 9/9；REFACTOR `python -m unittest tests.test_cli_policy_check tests.test_config tests.test_credentials tests.test_web -v` 为 18 tests、1 个既有 Windows skip；另运行 `python -m compileall -q forgeguard/cli.py tests/test_cli_policy_check.py` 与 `git diff --check -- forgeguard/cli.py tests/test_cli_policy_check.py`，均 exit `0`。
- RED/GREEN/REFACTOR — Task 3 初始轮：RED/GREEN focused command 均为 `python -m unittest tests.test_demo.DemoTests.test_mechanism_demo_is_deterministic -v`；RED 的 exact list 只有 4 个 demo events 而非 5，GREEN 1/1；另运行 `python -m forgeguard demo`，五行且 exit `0`。实际 REFACTOR sequence 是 `$first = python -m forgeguard demo`、`$second = python -m forgeguard demo`、`if (($first -join "`n") -ne ($second -join "`n")) { throw "demo output is not deterministic" }`、`python -m unittest tests.test_demo tests.test_policy_check -v`、`git diff --check -- forgeguard/demo.py tests/test_demo.py`；双次 demo output identical，selected 4/4，diff-check exit `0`。
- RED/GREEN/REFACTOR — Task 3 修复轮 1：focused RED command 为 `python -m unittest tests.test_demo.DemoTests.test_policy_check_demo_leaves_absolute_marker_uncreated -v`；先后观察 `run_demo` 不接受 `workspace`、再不接受 `marker_path`。GREEN commands 为 `python -m unittest tests.test_demo.DemoTests.test_policy_check_demo_leaves_absolute_marker_uncreated -v`、`python -m unittest tests.test_demo.DemoTests.test_mechanism_demo_is_deterministic -v`、`python -m forgeguard demo`；分别 1/1、1/1、五行 exit `0`。实际 REFACTOR sequence 是 `$first = python -m forgeguard demo`、`$second = python -m forgeguard demo`、`if (($first -join "`n") -ne ($second -join "`n")) { throw "demo output is not deterministic" }`、`python -m unittest tests.test_demo tests.test_policy_check -v`、`git diff --check -- forgeguard/demo.py tests/test_demo.py`；双次 demo output identical，selected 5/5，diff-check exit `0`。
- RED/GREEN/REFACTOR — Task 4 初始 README contract：RED/GREEN 使用同一 command body：`$text = Get-Content -LiteralPath 'README.md' -Raw`；`$required = @('## 只判断策略，不执行动作','policy-check --action-json','0=allow','2=require_approval','3=deny','4=输入、Action 解析或配置错误')`；`$missing = @($required | Where-Object { -not $text.Contains($_) })`；`if ($missing.Count -ne 0) { throw ('README missing: ' + ($missing -join ', ')) }`。RED 列出 6 个字符串全部缺失，GREEN 无 throw。两个实际 examples 为 `python -m forgeguard --workspace . policy-check --action-json '{"action":"run_command","arguments":{"argv":["git","status","--short"]}}'` 后接 `if ($LASTEXITCODE -ne 0) { throw "documented --action-json example failed" }`，以及 `'{"action":"read_file","arguments":{"path":"README.md"}}' | python -m forgeguard --workspace . policy-check` 后接 `if ($LASTEXITCODE -ne 0) { throw "documented stdin example failed" }`；两者均输出 allow JSON、exit `0`。selected regression `python -m unittest tests.test_cli_policy_check tests.test_demo -v` 为 11/11；`git diff --check -- README.md` exit `0`。
- RED/GREEN/REFACTOR — Task 4 修复轮 1 semantic check：RED/GREEN 使用同一 body：`$text = Get-Content -LiteralPath 'README.md' -Raw`；`$required = '命令读取全局 \`--workspace\`，并读取 \`--config\` 中的状态目录和命令白名单设置'`；`$obsolete = '\`--config\` 中的工作区、状态目录和命令白名单设置'`；`if (-not $text.Contains($required)) { throw "README missing corrected config/workspace semantics: $required" }`；`if ($text.Contains($obsolete)) { throw "README retains obsolete config/workspace semantics: $obsolete" }`。RED 观察到 missing corrected semantics、exit nonzero，但 exact numeric exit 未从 transcript 恢复；GREEN 同一 check 后打印 `README semantics: PASS`、exit `0`。
- RED/GREEN/REFACTOR — Task 4 修复轮 1 marker scan：原始 command 为 `$exampleHits = @(git grep -n -I -E 'YOUR_[A-Z0-9_]+' -- .)`；`$unexpectedExamples = @($exampleHits | Where-Object { $_ -notmatch '^README\.md:.*YOUR_PROVIDER_KEY' })`；`"total=$($exampleHits.Count) unexpected=$($unexpectedExamples.Count)"`；`$exampleHits`；`if ($unexpectedExamples.Count -ne 0) { $unexpectedExamples; throw "unexpected example marker" }`。结果 total 3/unexpected 2（plan 自引用）、exit nonzero，但 exact numeric exit 未从 transcript 恢复。更新后首行改为 `$exampleHits = @(git grep -n -I -E 'YOUR_[A-Z0-9_]+' -- . ':(exclude)docs/superpowers/2026-08-12-policy-check-plan.md')`，打印 `"example total=$($exampleHits.Count) unexpected=$($unexpectedExamples.Count)"`，其余过滤与 throw 相同；结果 total 1/unexpected 0、exit `0`。两个 README examples 同上，均 allow/exit `0`；selected regression `python -m unittest tests.test_cli_policy_check tests.test_demo -v` 为 11/11；`git diff --check -- README.md docs/superpowers/2026-08-12-policy-check-plan.md` exit `0`。上述缺失 command bodies 的证据来源是 `/root/task4_implementer` transcript recovery。
- RED/GREEN/REFACTOR — Task 5 transient evidence contract：修改本日志前运行 `$text = Get-Content -LiteralPath 'AGENT_LOG.md' -Raw`；`$section = [regex]::Match($text, '(?ms)^## \d{4}-\d{2}-\d{2}.*policy-check.*?(?=^## |\z)')`；若无 section 则 `Write-Error 'evidence contract: missing new dated policy-check section'; exit 1`；实际数组 command 为 `$required = @('Worktree/baseline','/root/task1_implementer','/root/task2_implementer','/root/task3_implementer','/root/task4_implementer','/root/task5_implementer','RED/GREEN/REFACTOR','Reviews','Human decisions','Commits','Final verification')`；随后运行 `$missing = @($required | Where-Object { -not $section.Value.Contains($_) })`；`if ($missing.Count -ne 0) { Write-Error ('evidence contract: missing fields: ' + ($missing -join ', ')); exit 1 }`；`Write-Output 'evidence contract: PASS'`。RED 为 `EXIT=1`、`Write-Error: evidence contract: missing new dated policy-check section`；补日志后相同 command GREEN 为 `EXIT=0`、`evidence contract: PASS`。未创建永久 grep 测试；本任务不改生产行为，无 REFACTOR。
- Reviews — Task 1：正式 spec `/root/task1_spec_review` 合规；其 diff-only TDD evidence warning 经 task-1-report 原始摘要、task commit 与 clean boundary 核实后解决。正式 quality `/root/task1_quality_review` Approved，Critical/Important/Minor 均无。实现者曾创建并行 Task 1 review agents；它们被中止，ledger 未记录其身份，且不计入正式证据，因为正式 review 必须由控制器顺序派发。
- Reviews — Task 2：spec `/root/task2_spec_review` 报告 2 个 Important（non-hashable Action name 泄漏 `TypeError`；malformed config type 逃逸 `invalid_config` boundary），均由 `/root/task2_implementer` 修复，`/root/task2_fix1_rereview` 复核。quality `/root/task2_quality_review` 报告 1 个 Important（过宽且不完整的 `TypeError` handling 会误分类 `allowed_commands:[1]` 并泄漏 `allowed_commands:'git'` 的 `AttributeError`），已修复，`/root/task2_fix2_rereview` APPROVED；0 open。
- Reviews — Task 3：spec `/root/task3_spec_review` 合规；historical RED/two-run evidence warning 依据 task-3-report 解决。quality `/root/task3_quality_review` 报告 1 个 Important（`side_effect_free` 缺少独立 absolute-marker 行为断言），已由实现者修复并经 `/root/task3_fix1_rereview` PASS。一个 Minor（`memory.close()` 在 policy-check/event emission 抛错时非 exception-safe）递延给最终 whole-branch review。
- Reviews — Task 4：spec `/root/task4_spec_review` 发现 README 把 workspace 错归 `--config`，与获批真实接口冲突；人类授权后修复，`/root/task4_fix1_rereview` APPROVE。quality `/root/task4_quality_review` 起初将 rendered diff 误读为含 JSON backslashes；控制器检查文件 bytes/lines 并执行两条 README 命令后，该 reviewer 撤回 Important 并 Approved。一个 Minor（README 的 error stdout/stderr 句可更明确只限 input、Action parsing、config errors）递延给最终 whole-branch review。
- Human decisions：获批输入为 `--action-json` 或 redirected stdin；option/stdin 冲突、空 redirected stdin、无 option 的 interactive stdin 属于 `invalid_input`。获批退出码为 allow `0`、require_approval `2`、deny `3`、input/Action-parse/config errors `4`。获批 schema 行为是复用现有 strict parser 和全部六种 Actions。获批 config 行为是 global `--workspace` 提供 workspace，`--config` 提供 `state_dir` 与 `allowed_commands`。获批成功输出是单行、sorted JSON stdout，字段恰为 `verdict`、`reason`、`risk`，Python `None` 序列化为 JSON `null`；上述 covered errors 输出单行 redacted JSON stdout 且 stderr 为空，此陈述不泛化到 argparse usage errors。用户在获知 README workspace/config 冲突和 scan 的 plan 自引用后说“那你解决一下问题”，授权按真实接口修文案，并让 scan 排除承载自身规则的 plan 文件。
- Commits：Task 1 `3bd9c100c4c5aa1adf537a9960965af236892c89`；Task 2 `94c7eabdd374e765a48026ed5ce0b6090d652f89`、`2ebabcc8c166c0988fade374e6758732c7bc4ef6`、`445b6f3ba1f01ae437a92fe8929a1ac33169b880`；Task 3 `62ede4d4155e0b453ccc052a0f3de4c4d5d10e3b`、`a2f61745305bbc11f57b84631d0e6550caf32a4b`；Task 4 `bf6a4882157f8f4b6d2d687160566c52d6844850`、`bc1abb6a162d05e4e3aef7a73b561be51305298f`。
- Final verification — pre-log Microtasks 1–4：specialty `python -m unittest tests.test_policy_check tests.test_cli_policy_check tests.test_demo -v` 为 14/14、exit `0`；full `python -m unittest discover -s tests -v` 为 54 tests、0 failures、仅 2 个既有 Windows skips、exit `0`。`python -m forgeguard demo` 精确输出 5 个 JSON events、exit `0`，第五项为 `5_policy_check`/`require_approval`/`arbitrary_code`/`side_effect_free:true`；compileall exit `0`；`git diff --check` exit `0`。credential scan command 以 `$credentialHits = @(git grep -n -I -E 'sk-[A-Za-z0-9_-]{16,}' -- .)` 收集 hits，并以明确 test/plan fixture allowlist 过滤，结果 13 hits、0 unexpected；self-excluding scan command 以 `$exampleHits = @(git grep -n -I -E 'YOUR_[A-Z0-9_]+' -- . ':(exclude)docs/superpowers/2026-08-12-policy-check-plan.md')` 收集 hits，并只允许 README `YOUR_PROVIDER_KEY`，结果 1 hit、0 unexpected。
- 未运行或未声称：没有 CI、PR 或远端证据；Task 5 不执行最终 whole-branch reviewer，该 reviewer 由控制器在本任务两阶段 review 后派发。
