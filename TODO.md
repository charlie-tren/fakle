# TODO

| ID | Priority | Duration | Input | Prereqs | Description |
|---|---|---|---|---|---|

## Closed

- **F3** Read the builds after the 02/11 fixes. DONE 06/11/2026: 04/11 and 05/11 passed
  first time; 03/11 and 06/11 failed their first runs. On 06/11 four of six general rounds
  were written; the two stuck rounds were a false "vague" (Hurghada only ever leads its
  headline, so it was not counted as a name) and a "trailing clause" note that never said
  which word. Fixed both, and the general rounds now pick two spares. The rebuild passed
  with the Trump round.

- **F1** Investigate the daily-puzzle failures of 14-15/10/2026. MIS-SCOPED 02/11/2026: not
  the Pages deploy. The `publish` job's "Fail the run if the build failed" step is where a
  failed BUILD surfaces; the 14/10 18:40Z run logged "general rounds failed, nothing
  written" after the gates rejected every fake. The same shape failed four builds on 02/11.
- **F2** Check whether Sonnet is failing the headline gates. DONE 02/11/2026: it was, and
  mostly the gates' fault. Of 74 rejections on 02/11, 35 were "new name": Title Case fakes
  failed it on every common word, and the note never said which name. Then "same story":
  a form model headline made clones of itself. Fixed in `gates.explain`, sentence case for
  the writer, and no form model; the next build passed first time.
