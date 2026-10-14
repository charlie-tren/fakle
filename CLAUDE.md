# Fakle

Daily game at charlietrenorden.com/fakle/: five rounds of four headlines from the last 24
hours, three real and one made up. Spec and plan: `hub-notes/docs/superpowers/`.

## What the content is for (Charlie, 11/10/2026)

The point is to show how insane the world is. Every rule below serves that.

- **Real headlines: the craziest of the day, nothing boring.** The bar is "Candidate named
  Hitler Mussolini elected mayor in Peru". Ordinary politics, markets, sport, diplomacy
  and policy are out however important. Trump mode picks the craziest Trump stories, not
  the routine ones.
- **A headline must read as a headline.** No questions, features, explainers or opinion
  ("Did a Baby Dinosaur Eat Its Own Kind? ..." was the example), and nothing ending in "...".
  Enforced in `pool.usable`.
- **A good fake is plausible, specific and quietly odd.** The example he liked: "Singapore
  installs smart misting poles along walkways to combat afternoon heat".
- **Fakes must not share a structure.** By the third day every fake read "X does Y amid Z"
  and was guessable. Each round gets its own shape (`prompts.SHAPES`) and
  `build.structure_clash` sends back repeats of an opening or a connector.
- **A fake must not be the same story as a real one.** "Ruto proposes camel milk tax" beside
  the real Ruto milk headline was the example. `gates.check_fake` compares content-word stems
  against its round (two shared) and the whole day (three shared).
- **One game, Trump last.** Five rounds: four general (no Trump headlines in them) and one
  all-Trump round with the day's craziest Trump stories. No mode toggle.
- **A fake follows its round's case** (`build.match_case`): an all-sentence-case fake beside
  Title Case reals was a tell.
- **No household-name brands or celebrities as a fake's subject.** "Apple patents smart
  watermelon scanner" was "too obviously fake": strange true stories are about obscure local
  players. Prompt rule.
- **No invented quotes from named people.** Quotes come from unnamed speakers only.
- **Rounds are grouped by broad area, but strangeness comes first** (14/10/2026). He asked
  whether fixed topic labels would block good stories; they would, so there is no fixed
  list. The picker groups where it can, never drops a stranger story to fit, and names
  each group after forming it; the page shows that name above the round, or nothing.
- **Each fake takes the form of one real in its round** (opening, punctuation, register),
  so the five vary as the outlets do. Fixed shapes were a house style of their own.
- **No story twice in a week.** Kid Rock turned up twice in three days. `memory.json` (served
  beside the puzzle, never committed) holds a week of real headlines; `build.echoes` drops
  a candidate sharing a two-word name or the same-story test with one.
- **Grim is not strange.** `build.DARK` keeps crashes, war and bodies out of the general rounds.
- **A fake must not be guessable by its style.** Players said they would soon spot a
  pattern. The tell on 14/10 was vagueness: "local council chief", "three pilots". So no
  quote shape, a `vague` gate (no name and no number fails), and a judge model that sees
  each round as a player does; a fake it spots is rewritten, up to twice, with its reason.
  **Anything asked of every fake becomes the new pattern**: "add a concrete detail" put a
  number in all five on the 13/10 trial, so a fake may carry a number only if its round does.
  Before adding a rule for all fakes, check the reals share that trait.
- **Players teach the writer.** Finished games post their picks anonymously to the
  `fakle-stats` Worker (`worker/`, D1). The end screen shows "Better than N% of today's
  players" and the review shows how many spotted each fake. Each build scores yesterday's
  fakes (`build.harvest`, 5+ players) and shows the writer the ones that fooled the most.
- **A fake that turns out to be true is the worst failure.** Fakes steer clear of every
  real story of the day; the gates in `gates.py` (allegations, invented names, overlap) are
  in code, not only in the prompt.

## Where things are

- Daily build: `.github/workflows/daily.yml`, deploys Pages from Actions. A dry run of past dates: `gh workflow run trial -f dates="YYYY-MM-DD"`. `puzzle.json` is
  never committed, so past fakes stay out of git history. Force a rebuild of today with
  `gh workflow run daily-puzzle -f force=true`.
- Providers: `llm.LADDER`, Gemini 3.6, 3.7, 3.8, 3.5, then Groq; one attempt each. Each
  forced rebuild spends ~10 Gemini calls of a 20/day-per-model allowance. Cloudflare is
  deliberately unused (its allowance is shared with Ghostwriters and Photocopy).
- A dropped mode prints which rule rejected each fake in the run log.
- Sources: One Story's history plus `pool.ODDITIES` (UPI, NY Post, Metro, Sky News weird
  sections, last 24h). Mirror and Daily Star weird feeds were filler; r/nottheonion via
  redlib was rate-limited (both 11/10/2026).

## Declined

- **An in-page "too easy / boring" feedback button** that feeds the prompt examples (offered
  11/10/2026; Charlie: "no dont add that"). Feedback reaches the rules through chat. Do not
  re-offer.
