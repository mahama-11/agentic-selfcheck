# Repair Events: github-pr-autonomy-repair-merge

Status: OPEN

## Event 1: service PATH missing gofmt
- Symptom: live webhook reached `NEEDS_REPAIR`, but repair executor failed.
- Evidence: `reports/github-pr-autonomy-live-webhook/reports/1778164067-ea38b5b0-4a20-11f1-82b1-4fb94885fcbe.report.failure.json`
- Error: `FileNotFoundError: [Errno 2] No such file or directory: 'gofmt'`
- Root cause: systemd service environment PATH did not expose `/usr/local/go/bin/gofmt`.
- Fix: repair executor now uses `shutil.which('gofmt')` with `/usr/local/go/bin/gofmt` fallback.
- Revalidation: manual repair for PR #3 succeeded and pushed fix commit.

## Event 2: repair worktree origin used HTTPS
- Symptom: manual repair could commit but failed push.
- Error: `fatal: could not read Username for 'https://github.com': No such device or address`
- Root cause: `gh repo clone` created an HTTPS origin in the repair worktree; non-interactive push could not authenticate.
- Fix: for `mahama-11/*`, repair executor sets origin URL to `github.com-mahama:<owner>/<repo>.git` before fetch/push.
- Revalidation: manual repair for PR #3 succeeded; new head `8d151c9abd536990de9d90e701c361f506513735`.

## Event 3: cleanup PR exposed product CI deletion-file bug
- Symptom: cleanup PR #4 deleting `pr_autonomy_repair_test.go` failed `Go baseline checks`.
- Evidence: GitHub run `25502616318`.
- Error: `stat pr_autonomy_repair_test.go: no such file or directory` from `gofmt -l $changed`.
- Root cause: platform-backend CI sends deleted `.go` files to `gofmt` instead of filtering to existing files.
- Action: cleanup PR #4 was closed and branch deleted to avoid a stuck autonomy loop.
- Follow-up: fix platform-backend CI deletion filtering separately, then remove the temporary validation file.

Status: CLOSED for agentic-selfcheck repair/merge slice. Remaining cleanup belongs to platform-backend CI hardening, not this control-plane implementation.
