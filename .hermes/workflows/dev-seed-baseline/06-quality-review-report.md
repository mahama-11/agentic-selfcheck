# 06 Quality / Security Review — dev-seed-baseline

角色：Quality/Security Reviewer
结论：**APPROVE**

## 复核范围

- 需求：`01-requirement.md`
- Developer handoff：`04-developer-summary.md`
- Git diff：
  - `/root/work/v/platform-backend`
  - `/root/work/v/ecommerce-backend`
  - `/root/work/agentic-selfcheck`

## 关键证据

### Platform devseed / guardrails

- `internal/config/config.go` 新增 `bootstrap.identity.dev_seed_enabled=false` 与 `force_rotate_password=false` 默认值，devseed 需要显式启用。
- `internal/modules/devseed/devseed.go`：
  - `DevSeedEnabled` 未开启直接跳过。
  - `GinMode != debug` 直接跳过。
  - 密码可由 `password_env` 覆盖；错误信息只包含 email，不打印密码。
  - 已有用户默认不更新 `password`，仅 `force_rotate_password=true` 时才重算 bcrypt。
- `config.local.yaml` 被 `.gitignore` 忽略，属于本地配置；本地启用 devseed 且 `force_rotate_password: false`。

### RBAC least privilege / stale cleanup

- `internal/modules/access/seed.go` 对内置角色声明式同步：`owner/admin/developer/viewer` 每次 seed 后删除不在默认声明内的 `role_permissions`。
- 当前语义：
  - `viewer`: `org.read/org.switch/team.read`，未授予 billing/oauth/logs/platform admin。
  - `developer`: `org.read/org.switch/team.read/org.usage.read/logs.read`，未授予 billing/oauth/platform admin。
  - `admin`: 含 billing/oauth/logs 管理能力，但不含 `platform.admin`。
  - `owner`: 含完整 owner 权限与 `platform.admin`。
- 测试 `TestSeedDefaultsRolePermissionSemanticsAndCleanup` 覆盖 viewer stale `billing.read` 清理与 required/forbidden grant 断言。

### Ecommerce projection fallback

- `SeedPresetCatalog()` 不再因 platform projection 启用而跳过本地 seed。
- `Detail/AddFavorite/CopyToMyTemplates/Use` 仅在 platform detail 返回 404（映射为 `gorm.ErrRecordNotFound`）时 fallback 到本地；非 404 错误继续向上返回。
- `listPlatformCatalog()` 在 platform projection 空列表时 fallback 到本地模板。
- 测试覆盖：空 projection + detail 404 fallback 的 list/detail/favorite/copy/use；非 404 detail 错误透传。

### SelfCheck gate

- `scripts/v_seed_baseline_gate.py` 登录后只记录 `token_obtained`，报告中剔除 login JSON，不打印 token/密码。
- RBAC gate 使用 required/forbidden grant 语义断言，不以 `role_permissions` 总行数作为通过条件。
- Ecommerce gate 校验 list 内容、detail id、use route/tool、favorite/copy 语义结果，不只是 HTTP 200。

## 已执行验证

```bash
cd /root/work/v/platform-backend && go test ./internal/modules/devseed ./internal/modules/access
# ok  platform-service/internal/modules/devseed  (cached)
# ok  platform-service/internal/modules/access   (cached)

cd /root/work/v/ecommerce-backend && go test ./internal/modules/templatecenter
# ok  ecommerce-service/internal/modules/templatecenter (cached)

cd /root/work/agentic-selfcheck && python3 -m py_compile scripts/v_seed_baseline_gate.py
# pass

cd /root/work/v/platform-backend && git diff --check
cd /root/work/v/ecommerce-backend && git diff --check
cd /root/work/agentic-selfcheck && git diff --check
# pass
```

## 非阻塞风险 / 建议

1. `devseed` guardrails 依赖显式开关 + `gin_mode=debug`。这满足本地 dev baseline，但未来若存在 debug 型共享环境，建议再增加环境名/允许 host/显式 `local_only` 之类的二次保险。
2. `devseed` 对匹配 email 的已有用户会设置 `is_platform_admin=true`、组织 owner 关系；当前仅在显式 debug devseed 下执行，符合本地 fixture 目标，但应避免在任何共享库/测试环境复用真实 email。
3. SelfCheck gate 仍直接依赖本地 Docker 容器名、DB 名与 schema；作为本地 L4 gate 可接受，但长期建议把这些参数化并在报告路径落盘，减少环境耦合。
4. 本轮未运行在线 SelfCheck gate 和全量 `go test ./...`；已执行受影响包测试与脚本编译。

## Verdict

**APPROVE** — 未发现需要阻断的安全/RBAC/幂等/生产防呆/边界泄漏问题。当前实现满足 dev-seed-baseline 验收口径；上述事项为后续加固建议。