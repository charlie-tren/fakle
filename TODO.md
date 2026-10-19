# TODO

| ID | Priority | Duration | Input | Prereqs | Description |
|---|---|---|---|---|---|
| F1 | 1.4 | 15 min | Auto | - | **Investigate the daily-puzzle failures of 14-15/10/2026.** Failed on 14/10 and once on 15/10 (`publish` job, "Process completed with exit code 1" right after "Creating Pages deployment"), then five successes later on 15/10. Looks transient, but check whether a day's puzzle was missed or double-published, and whether the Pages deploy step needs a retry. Logged 16/10/2026 after the failure emails were found unread. |
| F2 | 1.6 | 30 min | Auto | 20/10 run logs | **Check whether Sonnet is failing the headline gates.** The 19/10 puzzle, the first written by Claude, took three runs: two failed with "general rounds failed, nothing written" because the gates rejected Sonnet's fake headlines (new name, length, trailing clause, same story). That cost US$0.31 for the day, about US$9.40/month, against US$3-4 if it passed first time. On Gemini it passed first time on 16/10 and 17/10. If 20/10 also needs retries, find which gate rejects most often and fix the prompt, not the gate. |
