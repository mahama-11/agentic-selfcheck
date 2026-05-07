# 04 Developer Summary — dev-seed-baseline

角色：Developer（未做 final approval）

## Repair Addendum — Spec Reviewer blocker

### Platform `/root/work/v/platform-backend`
- 修复 devseed 默认会覆盖已有同邮箱用户 admin/org 状态的 blocker：
  - 新增 `bootstrap.identity.force_admin_state`（默认 `false`），并在 `config.local.yaml` 显式保持 `false`。
  - 缺失 dev admin 仍按原逻辑创建为 platform admin。
  - 已有用户在 `force_rotate_password=false` 且 `force_admin_state=false` 时只返回现有用户，不再更新密码、status、role、org/current_org、platform admin 标记或 membership。
  - `force_rotate_password=true` 仅轮换密码；`force_admin_state=true` 才执行 admin/org/status 修复并确保 membership/owner 关系。
- 增加 devseed 回归测试覆盖：默认不提权/不切 org/不轮换密码、`force_admin_state=true` 修复、已有 seed 用户幂等路径。

### Repair 修改文件
- `/root/work/v/platform-backend/internal/config/config.go`
- `/root/work/v/platform-backend/config.local.yaml`
- `/root/work/v/platform-backend/internal/modules/devseed/devseed.go`
- `/root/work/v/platform-backend/internal/modules/devseed/devseed_test.go`
- `/root/work/agentic-selfcheck/.hermes/workflows/dev-seed-baseline/04-developer-summary.md`

### Repair 验证

```bash
cd /root/work/v/platform-backend
gofmt -w internal/config/config.go internal/modules/devseed/devseed.go internal/modules/devseed/devseed_test.go
go test ./internal/modules/devseed ./internal/modules/access
```

结果：
```text
ok  	platform-service/internal/modules/devseed	(cached)
ok  	platform-service/internal/modules/access	(cached)
```

> Developer repair handoff only；未做 final approval。

## 本轮完成

### Platform `/root/work/v/platform-backend`
- 加固 devseed guardrails：
  - 新增 `bootstrap.identity.dev_seed_enabled` 显式开关，默认 `false`。
  - 新增 `bootstrap.identity.force_rotate_password`，默认 `false`；已有用户默认不再被 dev fixture 密码覆盖，只有显式开启才轮换。
  - `config.local.yaml` 显式启用本地 dev seed，但不强制轮换已有密码。
- 修复 RBAC least privilege：
  - `viewer` 仅保留 `org.read/org.switch/team.read`。
  - `developer` 保留组织切换/团队读取/用量读取/日志读取，不再授予 billing/oauth/platform admin。
  - `admin` 保留 billing/oauth/logs 管理型权限，但不授予 `platform.admin`。
  - `owner` 保留完整 owner 权限含 `platform.admin`。
- RBAC seed 改为对内置角色的 default role_permissions 进行声明式同步：每次 seed 会清理内置角色中不在默认声明内的 stale grants。
- 增加测试覆盖 devseed 显式开关、非 debug 跳过、默认不轮换密码、RBAC 语义与 stale cleanup。

### Ecommerce `/root/work/v/ecommerce-backend`
- 保持平台 projection 启用时仍 seed 本地模板 fixture，用作空 projection / 404 fallback baseline。
- 确认并测试 fallback 链路：`list -> detail -> favorite -> copy -> use`。
- 非 404 平台 detail 错误保持向上暴露，不静默 fallback。
- 增加 templatecenter handler/service 测试覆盖平台 projection 空列表、detail 404 fallback、favorite/copy/use fallback、非 404 错误透传。
- `/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend/internal/modules/templatecenter/service.go` 与主 ecommerce repo 的 critical `service.go` 内容已确认一致（`cmp` 返回 `0`）。

### SelfCheck `/root/work/agentic-selfcheck`
- 重写 `scripts/v_seed_baseline_gate.py` 的验收语义：
  - 登录只记录是否获得 token，不打印 token/密码。
  - RBAC 不再依赖 role_permissions 总行数，改为 required/forbidden grant 语义断言。
  - Ecommerce 校验 catalog 返回 item/content、detail 成功、use 成功，以及带 token 的 favorite/copy 成功。
  - report JSON 继续隐藏敏感值。
- 创建本文件：`.hermes/workflows/dev-seed-baseline/04-developer-summary.md`。

## 修改文件

### Platform
- `/root/work/v/platform-backend/internal/config/config.go`
- `/root/work/v/platform-backend/config.local.yaml`
- `/root/work/v/platform-backend/internal/modules/devseed/devseed.go`
- `/root/work/v/platform-backend/internal/modules/devseed/devseed_test.go`
- `/root/work/v/platform-backend/internal/modules/access/seed.go`
- `/root/work/v/platform-backend/internal/modules/access/access_test.go`

### Ecommerce
- `/root/work/v/ecommerce-backend/internal/modules/templatecenter/service.go`
- `/root/work/v/ecommerce-backend/internal/modules/templatecenter/handler_test.go`
- 同步核对：`/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend/internal/modules/templatecenter/service.go`

### SelfCheck
- `/root/work/agentic-selfcheck/scripts/v_seed_baseline_gate.py`
- `/root/work/agentic-selfcheck/.hermes/workflows/dev-seed-baseline/04-developer-summary.md`

## 已执行验证

```bash
cd /root/work/v/platform-backend
gofmt -w internal/config/config.go internal/modules/devseed/devseed.go internal/modules/devseed/devseed_test.go internal/modules/access/seed.go internal/modules/access/access_test.go
go test ./internal/modules/devseed ./internal/modules/access
```

结果：
```text
ok  	platform-service/internal/modules/devseed	1.785s
ok  	platform-service/internal/modules/access	0.597s
```

```bash
cd /root/work/v/ecommerce-backend
gofmt -w internal/modules/templatecenter/handler_test.go internal/modules/templatecenter/service.go
go test ./internal/modules/templatecenter
```

结果：
```text
ok  	ecommerce-service/internal/modules/templatecenter	1.342s
```

```bash
cd /root/work/agentic-selfcheck
python3 -m py_compile scripts/v_seed_baseline_gate.py
```

结果：通过（无输出）。

```bash
cmp -s /root/work/v/ecommerce-backend/internal/modules/templatecenter/service.go /root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend/internal/modules/templatecenter/service.go; echo $?
```

结果：
```text
0
```

## 未完成 / 风险

- 未运行在线 SelfCheck gate；该脚本依赖本机 Platform/Ecommerce 服务与 Docker Postgres 处于运行状态。
- 未执行全量 `go test ./...`；本轮执行的是受影响包的 targeted tests。
- Worktree `/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend` 仍有多处非本任务既有改动；本轮只核对 templatecenter critical `service.go` 同步，不处理其他 worktree 改动。
- 本总结仅为 Developer handoff，不作 final approval。