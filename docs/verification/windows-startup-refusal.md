# Windows resident startup refusal JSON

The manual full run [42123962071](https://github.com/YJBeetle/SWCLI/actions/runs/42123962071)
used SWCLI `769677ac6a2bdfb00e108c1606f419c0ef8e5f34`. Python 3.9/3.14 unit,
installed CLI and original-package jobs passed. Its complete public functional
plan passed 19 sets / 20 steps, with visible and properties receipts independently
verified (25 original JSON receipts). Equation-dimension verification passed too.
The overall native job nevertheless failed and is not accepted as a complete run.

## First failure

The later Windows-only boundary check calls `daemon start --attach-existing`
with no SW host and expects structured `ExistingHostNotFound`, without creating
an instance. The Task Scheduler action correctly wrote that refusal and exited.
The client raised RuntimeError for this expected result, then unconditionally
called `IRunningTask.Stop()` in `finally` after the action had already ended.
The native COM wrapper returned DISP_E_EXCEPTION with nested `0x8004130B`
(`SCHED_E_TASK_NOT_RUNNING`), replacing the first error with a traceback and
leaving `attach-without-host.json` empty. See Microsoft's
[Task Scheduler error constants](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-error-and-success-constants).

## Minimal correction

- Return the original structured startup failure, with its code and log path.
- Stop only queued/running startup tasks. Treat only the precise already-ended
  Task Scheduler error (direct or wrapped) as a benign state/stop race.
- Preserve other stop/delete/host-cleanup errors separately. They cannot replace
  the original startup error or suppress deletion of this unique task definition.
- Retain ready resident hosts and never kill an attached, unowned user host.
  No startup/native API retry, rollback, task restart or timeout change is added.

Five new regressions cover structured refusal, a real-shaped nested COM race,
non-benign cleanup errors, successful residence and shared-user-host preservation.
Before the fix, the first three failed with the same masking behavior. After it,
1623 source unit tests passed (21 platform skips). The shared VM was available
for read-only readiness checks but was then paused by another workflow; the
isolated dummy-task probe did not execute. No SW/VM was started, attached or
closed for this fix. Real hosted Windows boundary acceptance remains pending a
new targeted full run; portable tests are not native acceptance evidence.

## Original evidence SHA-256

| Original | SHA-256 |
| --- | --- |
| Native artifact 13462396826 ZIP | c04ac7d80ec236bc7d94c1590806ec4d6a9873b6a2bb4e7666cdda770f3acf44 |
| Failed native job log | 160704aa774e7cbe13a5895b1ff392415cda4980514ca172d08deb0055076aae |
| Full-plan runtime-sets.json | 52fddbafcca45b0f287a6b3c96d979e023072d980607ab184455d6d2a4200c4a |
| Properties receipt | 5105c62d4ee4cb0ca08bca0b307283c81c7bd7cc4f78acddb550cb16951ba9a9 |
| Visible receipt | 789917f7f82feced9f137c886f46ea0dc55c790a5c4caeaa6e70b1646070fa85 |
| Before-fix regression log | e97873386cdea4e4f942a28e4e3e886e482eab6472ae186eacbd42fa730eb361 |
| Final source-unit log | 60e3f14b1c9c93e07b8e6f0919ee09d9a42a9a8192c26b2bad9b08001e548c08 |

## Corrected original Windows run

[42173211739](https://github.com/YJBeetle/SWCLI/actions/runs/42173211739)
completed successfully at `9502f3ae014032fcdd4520f8f3b22f3ff700a39b`.
Independent checks of the original artifacts confirmed the complete 19-set /
20-step plan, 48 polygon cases, four depth writes and four equal-depth cases,
12 through-all cases, 15 exports, visible mode, metadata save/reopen and the
equation-driven dimension refusal. The attach-without-host receipt contains
`ExistingHostNotFound` without cleanup errors. The external visible user host
retains PID 9096 after its attached daemon stops; the endpoint is unreachable.

| Original | SHA-256 |
| --- | --- |
| Native artifact 13486381394 ZIP | 20e4202f7d83e53ab303e8a7e59452c094c6003f52b25100cc02d53569c08e65 |
| Dist artifact 13482380199 ZIP | 7376faed8a86b3166bed62d17a4c39163c1da502a4165622613d06966d601dd0 |
| Full-plan receipt | 2110db76e53963abe8397b125d50ae1c45178483b0c2996ec2c20ee3bc8ceae9 |
| Polygon receipt | cab7697f863fbe59b9f3c09766367ef71d808a912bdaeeb3d54969887edf2bf5 |

The original wheel and sdist match that source, including its historical
`sw-cli` entry point and version `0.1.0a16`; they are not acceptance of the later
command/MCP/a18 integration. This original upload contains no independent
scheduled-task terminal inventory, so that evidence remains unverified.

The next necessary full run will capture task names/path/state and explicit
process identity fields before and after lifecycle boundaries. Only uniquely
named SWCLI tasks and newly observed processes are compared. A bounded read-only
settling observation preserves each snapshot; inventory errors and persistent
new resources fail the gate. No startup/stop/native API is retried, and no user
host is terminated. Portable fixture tests cover the collector and assertions;
actual Windows collection remains pending the combined candidate's full run.
