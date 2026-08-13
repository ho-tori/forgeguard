# ForgeGuard 课程最终交付设计

日期：2026-08-13  
状态：用户已批准

## 1. 目标

在不伪造远端、CI、Release、个人身份或历史流程证据的前提下，把当前 `feat/policy-check` 分支整理为可尽快提交的本地候选版本。最终候选同时满足《AI4SE 期末项目 · 通用要求》和《AI4SE Final Project A · Coding Agent Harness》中能够由本地仓库客观完成的交付要求，并把必须由项目所有者通过个人账号或个人经历完成的事项压缩为明确清单。

最终托管仓库由用户确认为 `https://github.com/ho-tori/forgeguard`。分发采用 GitHub Release 而非在线部署，版本为 `v0.1.0`。截至设计批准时，仓库尚未 push，GitHub Release 尚未创建。

## 2. 事实与真实性边界

以下事实可以写入交付文档：

- 原项目主体已有实现、测试、Dockerfile、GitLab CI 配置和本地提交历史。
- `policy-check` 是一次真实的增量开发：使用 brainstorming、writing-plans、隔离 worktree、逐任务新鲜 subagent、TDD、两阶段 review 和 completion verification。
- policy-check 分支已有真实 commit、测试命令、RED/GREEN 摘要和 review 处置记录。
- 本地可以构建并验证 Release 资产，但这不等于 GitHub Release 已发布。

以下内容不得补写或冒充已完成：

- 原项目主体没有真实执行完整七步 Superpowers 流程，不能倒填为合规历史。
- 原项目没有实现前、不同类型 agent 的冷启动验证。最终阶段只能执行并记录“实现后补充冷启动审查”，不能冒充实现前验证。
- GitHub 尚未 push，不能声称远端分支、PR、Actions 或 Release 已存在或通过。
- `submission.jsonc` 中的身份和最终 Release URL 由用户亲自填写。
- `REFLECTION.md` 的最终个人反思必须由学生重写；AI 只能提供明确标注的参考示例。

## 3. 交付范围

### 3.1 需要最终校准的文档

- `SPEC.md`：保持系统规格，补充 policy-check 增量能力、Release 分发决策和真实未决项，避免把公网 WebUI 误写为本次交付方式。
- `PLAN.md`：移除“当前目录不是 Git 仓库”等过时表述；给真实已完成项补充 commit 证据；把远端 push、Actions 和 Release 明确标为所有者账号操作。
- `SPEC_PROCESS.md`：保留原项目流程偏离，加入实现后补充冷启动审查的真实输入、问题、误读和建议，明确其不能替代实现前要求。
- `README.md`：修正课程交付状态、仓库 URL、Release 获取/校验/运行方式、GitHub Actions 与 GitLab CI 的角色，以及 policy-check 错误输出声明的适用范围。
- `AGENT_LOG.md`：追加本轮真实设计、补充冷启动审查、文档/CI/Release 准备和验证记录；不修改早期 `19:xx` 占位为虚构时间。
- `REFLECTION.md`：直接放置一份 1500–2500 中文字的 AI 参考示例，内容只使用仓库中可验证的开发问题；顶部醒目标注“AI 生成示例，必须由学生结合真实经历重写，不可直接提交”。

`submission.jsonc` 不修改，由用户最终填写。

### 3.2 CI

保留课程硬性要求的 `.gitlab-ci.yml` 及其 `unit-test` job。新增 `.github/workflows/ci.yml`，使实际 GitHub 托管仓库在 push 后自动执行：

- 全量 `unittest`；
- Mock LLM 机制演示；
- `compileall`；
- 凭据和示例占位符扫描；
- Docker image build。

本地只能验证 workflow 结构、命令一致性和能够运行的检查。只有实际 push 后的 GitHub Actions 页面能够形成远端通过证据。

### 3.3 Release 准备

以 `v0.1.0` 为 Release 版本，生成：

- Python 源码分发包；
- `SHA256SUMS.txt`；
- Release Notes。

Release Notes 说明 ForgeGuard 的治理主贡献、离线 Mock demo、policy-check、副作用边界、安装方式、已知限制和校验步骤。源码包必须在临时隔离目录中完成安装 smoke test，并成功运行 `forgeguard demo`。本地资产只标记为“待上传”，不能写成已发布。

## 4. 补充冷启动审查

派发一个全新、不同模型的 subagent，只向其提供 `SPEC.md` 与 `PLAN.md`，要求其以陌生实现者视角：

1. 选择 1–2 个任务说明准备如何实现；
2. 遇到规格不确定时暂停并提出问题；
3. 指出可能误读、缺陷或缺失验收条件；
4. 不读取代码、不修改文件。

结果写入 `SPEC_PROCESS.md` 与 `AGENT_LOG.md`，包括 agent 身份、提供的上下文、问题、误读和采纳/不采纳决定。标题必须明确为“实现后补充冷启动审查”；不得声称它发生在实现前，也不得把建议自动当作已实现事实。

## 5. 执行组织

所有修改都在 `E:\project\.worktrees\feat\policy-check` 的 `feat/policy-check` 分支完成，不直接修改 `main`。按以下逻辑单元分别提交：

1. 补充冷启动审查与规格过程证据；
2. 课程交付文档校准；
3. GitHub Actions 与 Release 资产准备；
4. 反思参考示例；
5. 最终验证证据。

涉及行为或自动化检查的变更先写失败的契约测试或静态断言，再进行最小修改；纯事实性文档更新使用内容契约检查。每个逻辑单元完成后运行 scoped verification，并保持独立 commit。

## 6. 错误与缺口处理

- GitHub 不可访问时，不尝试伪造远端检查；保留准确的手工步骤。
- Docker daemon 不可用时，报告本机未验证 Docker build，等待 GitHub Actions 形成真实证据。
- Release URL 在 Release 创建前保持由用户填写，不写假 URL。
- 发现文档与实现冲突时以已测试实现和获批 policy-check 契约为准，并记录修正原因。
- 发现课程要求只能由历史前置行为满足时，明确标为偏离，不用事后文案消除事实差异。

## 7. 最终验证

候选版本完成前必须重新运行并记录：

- policy-check 专项测试；
- 全量 unittest；
- Mock LLM demo；
- Python compileall；
- `git diff --check`；
- 凭据与示例占位符扫描；
- `.gitlab-ci.yml` 的 `unit-test` job 和 GitHub Actions 必需步骤静态契约检查；
- Release 源码包内容、SHA-256 校验和、隔离安装与 demo smoke test；
- `git status --short`。

成功声明必须区分“本地已验证”和“远端待所有者操作”。

## 8. 最终交接

本地候选完成后，项目所有者仍需亲自：

1. 将 `REFLECTION.md` 的 AI 示例重写为个人反思，并保留所需 AI 润色标注；
2. 填写 `submission.jsonc` 的学号、姓名、仓库与最终 Release URL；
3. 修正本地 `origin` 中现有的终端控制字符，push GitHub；
4. 确认 GitHub Actions 最后一次运行全部通过；
5. 创建 `v0.1.0` GitHub Release，上传源码包、`SHA256SUMS.txt` 和 Release Notes，再填写真实 URL。

未完成上述账号和个人写作步骤前，版本只能称为“本地准提交候选”，不能称为完整最终提交。
