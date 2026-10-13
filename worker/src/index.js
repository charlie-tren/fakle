/* Today's results, anonymously. A finished game posts its five picks and its score;
   anyone can read the day's totals back. No cookie, no IP, no player ID is kept.

     POST /result   {date, id, picks: [0-3 x rounds], score}
     GET  /stats?date=&id=   {players, scores: [count per score], rounds: [[count per position]]} */

const ORIGIN = /^https:\/\/([a-z0-9-]+\.)*charlietrenorden\.com$/;

const cors = (req) => {
  const o = req.headers.get("Origin") || "";
  return ORIGIN.test(o) ? { "Access-Control-Allow-Origin": o, "Vary": "Origin" } : {};
};

const json = (req, body, extra) => new Response(JSON.stringify(body), {
  headers: { "Content-Type": "application/json", ...cors(req), ...(extra || {}) },
});

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const ID = /^[0-9TZ]{0,20}$/;

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: {
        ...cors(req), "Access-Control-Allow-Methods": "GET, POST", "Access-Control-Allow-Headers": "Content-Type" } });
    }

    if (url.pathname === "/result" && req.method === "POST") {
      let b;
      try { b = await req.json(); } catch (e) { return new Response("", { status: 400, headers: cors(req) }); }
      const ok = b && DATE.test(b.date) && ID.test(b.id || "") && Array.isArray(b.picks) &&
        b.picks.length >= 1 && b.picks.length <= 6 && b.picks.every((p) => Number.isInteger(p) && p >= 0 && p <= 3) &&
        Number.isInteger(b.score) && b.score >= 0 && b.score <= b.picks.length;
      if (!ok) return new Response("", { status: 400, headers: cors(req) });
      await env.DB.prepare("INSERT INTO results (date, build, picks, score) VALUES (?, ?, ?, ?)")
        .bind(b.date, b.id || "", b.picks.join(""), b.score).run();
      return new Response("", { status: 204, headers: cors(req) });
    }

    if (url.pathname === "/stats" && req.method === "GET") {
      const date = url.searchParams.get("date") || "";
      const id = url.searchParams.get("id") || "";
      if (!DATE.test(date) || !ID.test(id)) return new Response("", { status: 400, headers: cors(req) });
      const { results } = await env.DB.prepare("SELECT picks, score FROM results WHERE date = ? AND build = ?")
        .bind(date, id).all();
      const n = results.reduce((m, r) => Math.max(m, r.picks.length), 0);
      const scores = new Array(n + 1).fill(0);
      const rounds = Array.from({ length: n }, () => [0, 0, 0, 0]);
      for (const r of results) {
        scores[r.score] += 1;
        [...r.picks].forEach((p, i) => { rounds[i][Number(p)] += 1; });
      }
      return json(req, { players: results.length, scores, rounds }, { "Cache-Control": "public, max-age=60" });
    }

    return new Response("", { status: 404 });
  },
};
