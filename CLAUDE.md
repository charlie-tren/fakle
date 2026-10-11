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
- **A fake that turns out to be true is the worst failure.** Fakes steer clear of every
  real story of the day; the gates in `gates.py` (allegations, invented names, overlap) are
  in code, not only in the prompt.

## Where things are

- Daily build: `.github/workflows/daily.yml`, deploys Pages from Actions. `puzzle.json` is
  never committed, so past fakes stay out of git history. Force a rebuild of today with
  `gh workflow run daily-puzzle -f force=true`.
- Providers: `llm.LADDER`, Gemini 3.6 then 3.7 then Groq; one attempt each. Cloudflare is
  deliberately unused (its allowance is shared with Ghostwriters and Photocopy).
- A dropped mode prints which rule rejected each fake in the run log.
