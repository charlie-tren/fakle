# TODO

| ID | Priority | Duration | Input | Prereqs | Description |
|---|---|---|---|---|---|
| F3 | 1.5 | 5 min | Auto | 03/11 build | **Read the 03/11 build log.** First scheduled build with the 02/11 fixes (named rejection notes, sentence case, no form model, the spare round replacing a fake the judge still catches, a second try per feed). Check it passed first time, count rejections by gate, and look for "replaced by the spare round" and any `oddities:` line with its status code. If it needed retries, fix the gate that rejected most. |

## Closed

- **F1** Investigate the daily-puzzle failures of 14-15/10/2026. MIS-SCOPED 02/11/2026: not
  the Pages deploy. The `publish` job's "Fail the run if the build failed" step is where a
  failed BUILD surfaces; the 14/10 18:40Z run logged "general rounds failed, nothing
  written" after the gates rejected every fake. The same shape failed four builds on 02/11.
- **F2** Check whether Sonnet is failing the headline gates. DONE 02/11/2026: it was, and
  mostly the gates' fault. Of 74 rejections on 02/11, 35 were "new name": Title Case fakes
  failed it on every common word, and the note never said which name. Then "same story":
  a form model headline made clones of itself. Fixed in `gates.explain`, sentence case for
  the writer, and no form model; the next build passed first time.
