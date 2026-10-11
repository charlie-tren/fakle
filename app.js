(function () {
  "use strict";
  var mode = new URLSearchParams(location.search).get("mode") === "trump" ? "trump" : "normal";
  var $ = function (id) { return document.getElementById(id); };
  var store = {
    get: function (k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  };
  var PROGRESS = "fakle:" + mode + ":progress";
  var STATS = "fakle:" + mode + ":stats";

  var state = { mode: mode, date: null, picks: [], done: false };
  window.fakleState = state;
  var rounds = null;
  var current = 0;

  document.querySelectorAll(".modes a").forEach(function (a) {
    if (a.dataset.mode === mode) a.setAttribute("aria-current", "page");
  });

  // The F-A-K-L-E wordmark is the progress row: one letter per round, in the header
  // while playing and large on the end screen.
  function paintLetters() {
    document.querySelectorAll(".letters").forEach(function (ol) {
      Array.prototype.forEach.call(ol.children, function (li, i) {
        var p = state.picks[i];
        li.className = p !== undefined ? (p === rounds[i].fake ? "right" : "wrong")
          : (!state.done && i === current ? "now" : "");
      });
    });
  }

  function score() {
    return state.picks.filter(function (p, i) { return p === rounds[i].fake; }).length;
  }

  function row(h, j, r, picked) {
    var li = document.createElement("li");
    li.className = "headline";
    var text = document.createElement("span");
    text.className = "text";
    text.textContent = h.text;
    li.appendChild(text);
    if (picked === undefined) {
      li.tabIndex = 0;
      li.setAttribute("role", "button");
      li.addEventListener("click", function () { pick(j); });
      li.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(j); }
      });
      return li;
    }
    if (j === r.fake) {
      li.classList.add("is-fake");
      var tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = "Fake";
      li.appendChild(tag);
    } else {
      var a = document.createElement("a");
      a.href = h.url; a.target = "_blank"; a.rel = "noopener";
      a.textContent = h.source;
      li.appendChild(a);
    }
    if (j === picked) li.classList.add(j === r.fake ? "right" : "wrong");
    return li;
  }

  function render(i) {
    current = i;
    var r = rounds[i];
    var picked = state.picks[i];
    $("progress").textContent = "Round " + (i + 1) + " of " + rounds.length + " \u00b7 " + score() + " right";
    var ol = $("round");
    ol.innerHTML = "";
    r.headlines.forEach(function (h, j) { ol.appendChild(row(h, j, r, picked)); });
    $("next").hidden = picked === undefined;
    $("next").textContent = i === rounds.length - 1 ? "See result" : "Next";
    paintLetters();
  }

  function pick(j) {
    if (state.picks[current] !== undefined) return;
    state.picks[current] = j;
    store.set(PROGRESS, { date: state.date, picks: state.picks });
    render(current);
    $("next").focus();
  }

  $("next").addEventListener("click", function () {
    if (current + 1 >= rounds.length) return finish();
    render(current + 1);
    $("round").querySelector(".headline").focus();
  });

  function recordStats() {
    var st = store.get(STATS) || { last: null, streak: 0, best: 0, played: 0 };
    if (st.last === state.date) return st;
    var y = new Date(state.date + "T00:00:00Z");
    y.setUTCDate(y.getUTCDate() - 1);
    st.streak = st.last === y.toISOString().slice(0, 10) ? st.streak + 1 : 1;
    st.best = Math.max(st.best, st.streak);
    st.played += 1;
    st.last = state.date;
    return store.set(STATS, st) ? st : null;
  }

  function finish() {
    state.done = true;
    var s = score();
    $("round").innerHTML = "";
    $("next").hidden = true;
    $("progress").textContent = "";
    $("end").hidden = false;
    $("score").textContent = s + " of " + rounds.length;
    var d = state.date.split("-");
    // A target for a fake spotted, a clown for one that fooled you.
    var squares = rounds.map(function (r, i) {
      return String.fromCodePoint(state.picks[i] === r.fake ? 0x1F3AF : 0x1F921);
    }).join("");
    $("share-text").textContent = "Fakle" + (mode === "trump" ? " Trump" : "") + " " +
      Number(d[2]) + "/" + Number(d[1]) + " " + s + "/" + rounds.length + "\n" + squares;
    var st = recordStats();
    paintLetters();
    $("streak").textContent = st ? "Streak " + st.streak + " \u00b7 best " + st.best : "";
    countdown();
  }

  function copyFallback(t) {
    var ta = document.createElement("textarea");
    ta.value = t;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
    return ok;
  }

  $("share").addEventListener("click", function () {
    var t = $("share-text").textContent + "\nhttps://charlietrenorden.com/fakle/" + (mode === "trump" ? "?mode=trump" : "");
    var say = function (ok) { $("share").textContent = ok ? "Copied" : "Copy failed"; };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t).then(function () { say(true); }, function () { say(copyFallback(t)); });
    } else {
      say(copyFallback(t));
    }
  });

  function countdown() {
    var syd = new Date(new Date().toLocaleString("en-US", { timeZone: "Australia/Sydney" }));
    var next = new Date(syd);
    next.setHours(9, 0, 0, 0);   // the build lands between about 05:00 and 09:00
    if (next <= syd) next.setDate(next.getDate() + 1);
    var mins = Math.round((next - syd) / 60000);
    $("countdown").textContent = "Next Fakle in " + Math.floor(mins / 60) + "h " + (mins % 60) + "m";
  }

  // A failed build leaves yesterday's file up. It may still be played until midday
  // Sydney, because the new one can land late; after that it is not today's Fakle.
  function fresh(date) {
    var parts = {};
    new Intl.DateTimeFormat("en-CA", { timeZone: "Australia/Sydney", year: "numeric", month: "2-digit",
      day: "2-digit", hour: "2-digit", hourCycle: "h23" }).formatToParts(new Date())
      .forEach(function (x) { parts[x.type] = x.value; });
    var today = parts.year + "-" + parts.month + "-" + parts.day;
    if (date === today) return true;
    var y = new Date(today + "T00:00:00Z");
    y.setUTCDate(y.getUTCDate() - 1);
    return date === y.toISOString().slice(0, 10) && Number(parts.hour) < 12;
  }

  fetch("puzzle.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (p) {
    rounds = p[mode];
    state.date = p.date;
    if (!rounds || !fresh(p.date)) { $("none").hidden = false; return; }
    var saved = store.get(PROGRESS);
    if (saved && saved.date === p.date && Array.isArray(saved.picks)) state.picks = saved.picks.slice(0, rounds.length);
    if (state.picks.length >= rounds.length) finish(); else render(state.picks.length);
  }).catch(function () { $("none").hidden = false; });
})();
