# 05 Spec Review Report — dev-seed-baseline

角色：Spec Reviewer（re-review）
结论：APPROVE

## 复审范围

本次仅复审 developer 针对 devseed mutation blocker 的修复是否关闭，重点检查：

- `/root/work/v/platform-backend/internal/config/config.go`
- `/root/work/v/platform-backend/config.local.yaml`
- `/root/work/v/platform-backend/internal/modules/devseed/devseed.go`
- `/root/work/v/platform-backend/internal/modules/devseed/devseed_test.go`
- `/root/work/agentic-selfcheck/.hermes/workflows/dev-seed-baseline/04-developer-summary.md`

## 验证执行

```text
cd /root/work/v/platform-backend && go test ./internal/modules/devseed ./internal/modules/access
ok  	platform-service/internal/modules/devseed	(cached)
ok  	platform-service/internal/modules/access	(cached)
```

## 复审结果

- **缺失 dev admin 仍会创建为 platform admin**：`ensureDevAdminUser()` 在用户不存在时创建 `role=platform_admin`、`org_role=owner`、`is_platform_admin=true`，并由 `created || forceAdminState` 路径确保 membership。
- **默认不再突变已有同邮箱用户身份状态**：已有用户路径默认只返回现有用户；在 `force_rotate_password=false` 且 `force_admin_state=false` 时不会更新 password/status/role/org/current_org/last_active_org/platform admin 标记，也不会新增 dev admin membership。
- **`force_rotate_password` 仅轮换密码**：已有用户路径中该开关只写入 `password`；admin/org/status 修复受 `force_admin_state` 独立控制。
- **`force_admin_state` 显式修复 admin/org 状态**：该开关开启时才更新 active/platform_admin/owner/org/current_org/last_active_org/is_platform_admin，并确保 org owner/billing email 与 membership。
- **配置默认安全**：`config.go` 默认 `dev_seed_enabled=false`、`force_rotate_password=false`、`force_admin_state=false`；`config.local.yaml` 本地启用 dev seed，但显式保持 `force_rotate_password=false`、`force_admin_state=false`。
- **测试覆盖并通过**：新增/现有 devseed 测试覆盖显式 enable、非 debug 跳过、创建缺失 admin、默认不轮换密码、默认不提权/不切 org、`force_admin_state=true` 修复、已有 seed 用户幂等；受影响包测试通过。

## 非阻塞观察

- `force_rotate_password=true` 对“已有非 admin 同邮箱用户只轮换密码、不提权/不切 org”的语义目前主要由实现结构保证；后续可补一个更直接的回归用例，但不影响本次 blocker 关闭判断。

## 结论

原 `REQUEST_CHANGES` blocker（dev admin seed 默认反复覆盖已有用户 admin/org state）已修复并验证通过。本次 spec reviewer re-review 结论为 **APPROVE**。
