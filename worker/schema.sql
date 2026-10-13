CREATE TABLE IF NOT EXISTS results (
  date TEXT NOT NULL,
  build TEXT NOT NULL,
  picks TEXT NOT NULL,
  score INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS results_day ON results (date, build);
