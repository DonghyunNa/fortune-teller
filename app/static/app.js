"use strict";

// ---------- helpers ----------
function $(sel, root) { return (root || document).querySelector(sel); }
function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const k in attrs) {
      if (k === "class") node.className = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else node.setAttribute(k, attrs[k]);
    }
  }
  (children || []).forEach(function (c) {
    if (c == null) return;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  });
  return node;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// interpretation: \n\n => <p> blocks
function interpretationEl(text) {
  const wrap = el("div", { class: "interpretation" });
  String(text).trim().split(/\n\s*\n/).forEach(function (para) {
    const p = el("p");
    p.innerHTML = escapeHtml(para.trim()).replace(/\n/g, "<br />");
    wrap.appendChild(p);
  });
  return wrap;
}

function noticeEl(kind, msg) {
  return el("div", { class: "notice " + kind }, [msg]);
}

function loadingEl(msg) {
  return el("div", { class: "loading" }, [el("div", { class: "spinner" }), msg || "운세를 풀이하는 중..."]);
}

// omit empty optional fields; trims strings
function putOptional(body, key, raw) {
  if (raw == null) return;
  const v = typeof raw === "string" ? raw.trim() : raw;
  if (v === "" || v == null) return;
  body[key] = v;
}

// birth_hour: "" => null (모름, 0시와 구분); otherwise int
function readBirthHour(selectEl) {
  const v = selectEl.value;
  return v === "" ? null : parseInt(v, 10);
}

// populate 0~23 hour options on a select (keeps existing first "모름" option)
function fillHours(sel) {
  const labels = [
    "子 자시", "丑 축시", "丑 축시", "寅 인시", "寅 인시", "卯 묘시", "卯 묘시",
    "辰 진시", "辰 진시", "巳 사시", "巳 사시", "午 오시", "午 오시", "未 미시",
    "未 미시", "申 신시", "申 신시", "酉 유시", "酉 유시", "戌 술시", "戌 술시",
    "亥 해시", "亥 해시", "子 자시"
  ];
  for (let h = 0; h < 24; h++) {
    const hh = String(h).padStart(2, "0");
    sel.appendChild(el("option", { value: String(h) }, [hh + ":00  (" + labels[h] + ")"]));
  }
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-json */ }
  return { ok: res.ok, status: res.status, data: data };
}

// pull a friendly message out of a 422 (FastAPI validation) detail
function detailMessage(data) {
  if (!data) return "요청 처리에 실패했습니다.";
  const d = data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map(function (e) {
      const loc = Array.isArray(e.loc) ? e.loc.filter(function (x) { return x !== "body"; }).join(".") : "";
      return (loc ? loc + ": " : "") + (e.msg || "");
    }).join(" / ");
  }
  return "요청 처리에 실패했습니다.";
}

// LLM-failed: render calc result + a warn notice instead of error
function interpretationBlock(data) {
  if (data.interpretation) {
    return el("div", { class: "block" }, [el("h3", null, ["풀이"]), interpretationEl(data.interpretation)]);
  }
  if (data.error) {
    return noticeEl("warn", "풀이 생성 실패: " + data.error + " (계산 결과는 위에 표시됩니다)");
  }
  return noticeEl("warn", "풀이가 생성되지 않았습니다. (API 키 미설정 시 발생할 수 있습니다)");
}

// ---------- tab switching ----------
$$(".tab").forEach(function (tab) {
  tab.addEventListener("click", function () {
    const name = tab.dataset.tab;
    $$(".tab").forEach(function (t) { t.classList.toggle("is-active", t === tab); });
    $$(".panel").forEach(function (p) { p.classList.toggle("is-active", p.id === "panel-" + name); });
  });
});

// ---------- leap-month toggle (음력 선택 시만 노출) ----------
function wireLeap(prefix) {
  const field = $("#" + prefix + "-leap-field");
  const radios = $$('input[name="' + prefix + '-calendar"]');
  function sync() {
    const lunar = radios.some(function (r) { return r.checked && r.value === "lunar"; });
    field.hidden = !lunar;
    if (!lunar) { const cb = $("#" + prefix + "-is_leap_month"); if (cb) cb.checked = false; }
  }
  radios.forEach(function (r) { r.addEventListener("change", sync); });
  sync();
}

// ---------- generic submit wrapper ----------
function wireForm(formId, resultId, button, handler) {
  const form = $("#" + formId);
  const result = $("#" + resultId);
  form.addEventListener("submit", async function (ev) {
    ev.preventDefault();
    const btn = $(".submit", form);
    const original = btn.textContent;
    btn.disabled = true;
    result.innerHTML = "";
    result.appendChild(loadingEl());
    try {
      const nodes = await handler();
      result.innerHTML = "";
      nodes.forEach(function (n) { if (n) result.appendChild(n); });
    } catch (err) {
      result.innerHTML = "";
      result.appendChild(noticeEl("error", "네트워크 오류: " + (err && err.message ? err.message : err)));
    } finally {
      btn.disabled = false;
      btn.textContent = original;
    }
  });
}

// ---------- renderers ----------
function pillarsTable(pillars) {
  const order = [["year", "연주"], ["month", "월주"], ["day", "일주"], ["hour", "시주"]];
  const head = el("tr", null, [el("th", null, [""])].concat(order.map(function (o) { return el("th", null, [o[1]]); })));

  function row(label, pick) {
    const cells = [el("th", null, [label])];
    order.forEach(function (o) {
      const p = pillars[o[0]];
      if (!p) { cells.push(el("td", { class: "unknown" }, ["미상"])); return; }
      cells.push(pick(p));
    });
    return el("tr", null, cells);
  }

  const tbody = el("tbody", null, [
    row("천간", function (p) { return el("td", null, [p.stem]); }),
    row("지지", function (p) { return el("td", null, [p.branch]); }),
    row("60갑자", function (p) { return el("td", { class: "ganzhi" }, [p.sexagenary]); }),
    row("오행", function (p) { return el("td", null, [p.stem_element + " · " + p.branch_element]); }),
  ]);

  return el("table", { class: "pillar-table" }, [el("thead", null, [head]), tbody]);
}

function elementsChips(elements) {
  const order = ["목", "화", "토", "금", "수"];
  const wrap = el("div", { class: "elements" });
  order.forEach(function (name) {
    if (!(name in elements)) return;
    wrap.appendChild(el("span", { class: "el-chip el-" + name }, [
      el("span", { class: "el-name" }, [name]),
      el("span", { class: "el-count" }, [String(elements[name])]),
    ]));
  });
  return wrap;
}

function kv(pairs) {
  const dl = el("dl", { class: "kv" });
  pairs.forEach(function (p) {
    if (p[1] == null || p[1] === "") return;
    dl.appendChild(el("dt", null, [p[0]]));
    dl.appendChild(el("dd", null, [String(p[1])]));
  });
  return dl;
}

// ================= SAJU =================
fillHours($("#saju-birth_hour"));
wireLeap("saju");
wireForm("form-saju", "result-saju", null, async function () {
  const cal = $('input[name="saju-calendar"]:checked').value;
  const body = {
    birth_date: $("#saju-birth_date").value,
    birth_hour: readBirthHour($("#saju-birth_hour")),
    calendar: cal,
    is_leap_month: cal === "lunar" ? $("#saju-is_leap_month").checked : false,
  };
  const minute = $("#saju-birth_minute").value;
  if (minute !== "") body.birth_minute = parseInt(minute, 10);
  putOptional(body, "focus", $("#saju-focus").value);
  putOptional(body, "tone", $("#saju-tone").value);
  putOptional(body, "gender", $("#saju-gender").value);
  putOptional(body, "context", $("#saju-context").value);

  const r = await postJSON("/saju/reading", body);
  if (r.status === 422 || (!r.ok && r.status !== 200)) {
    return [noticeEl("error", "계산 오류: " + detailMessage(r.data))];
  }
  const d = r.data;
  const p = d.pillars;

  const calcBlock = el("div", { class: "block" }, [
    el("h3", null, ["사주팔자"]),
    pillarsTable(p.pillars),
  ]);
  if (p.hour_unknown) calcBlock.appendChild(el("p", { class: "hint" }, ["* 태어난 시 미상 — 시주는 계산에서 제외(미상)됩니다."]));

  const elemBlock = el("div", { class: "block" }, [
    el("h3", null, ["오행 분포"]),
    elementsChips(p.elements),
    kv([
      ["일간(日干)", p.day_master + " (" + p.day_master_element + ")"],
    ]),
  ]);

  return [calcBlock, elemBlock, interpretationBlock(d)];
});

// ================= DAILY =================
fillHours($("#daily-birth_hour"));
wireLeap("daily");
wireForm("form-daily", "result-daily", null, async function () {
  const cal = $('input[name="daily-calendar"]:checked').value;
  const body = {
    calendar: cal,
    is_leap_month: cal === "lunar" ? $("#daily-is_leap_month").checked : false,
    birth_hour: readBirthHour($("#daily-birth_hour")),
  };
  putOptional(body, "target_date", $("#daily-target_date").value);
  putOptional(body, "birth_date", $("#daily-birth_date").value);
  const minute = $("#daily-birth_minute").value;
  if (minute !== "") body.birth_minute = parseInt(minute, 10);
  putOptional(body, "focus", $("#daily-focus").value);
  putOptional(body, "tone", $("#daily-tone").value);
  putOptional(body, "gender", $("#daily-gender").value);
  putOptional(body, "context", $("#daily-context").value);

  const r = await postJSON("/daily/reading", body);
  if (r.status === 422 || (!r.ok && r.status !== 200)) {
    return [noticeEl("error", "계산 오류: " + detailMessage(r.data))];
  }
  const d = r.data;
  const daily = d.daily;
  const g = daily.day_ganzhi;

  const ganzhiBlock = el("div", { class: "block ganzhi-card" }, [
    el("div", { class: "tc-position" }, [daily.target_date + " 의 일진(日辰)"]),
    el("div", { class: "ganzhi-big" }, [g.sexagenary]),
    el("div", { class: "ganzhi-sub" }, [
      g.stem + "(" + g.stem_element + ") · " + g.branch + "(" + g.branch_element + ")",
    ]),
  ]);

  const blocks = [ganzhiBlock];

  if (daily.personalized) {
    const ef = daily.element_focus || {};
    const detail = el("div", { class: "block" }, [
      el("h3", null, ["개인화 풀이 근거"]),
      kv([
        ["내 일간(日干)", daily.day_master],
        ["오늘 천간과의 관계(십신)", daily.relation_ten_god],
        ["오늘 강조 오행", (ef.day_stem_element || "") + " · " + (ef.day_branch_element || "")],
        ["오늘 보강되는 기운", (ef.reinforced && ef.reinforced.length) ? ef.reinforced.join(", ") : "특별히 없음"],
      ]),
    ]);
    if (ef.user_elements) {
      detail.appendChild(el("p", { class: "hint", style: "margin-top:14px" }, ["내 오행 분포"]));
      detail.appendChild(elementsChips(ef.user_elements));
    }
    blocks.push(detail);
  } else {
    blocks.push(noticeEl("warn", "생년월일을 입력하지 않아 일진 전반의 기운만 풀이합니다 (비개인화)."));
  }

  blocks.push(interpretationBlock(d));
  return blocks;
});

// ================= TAROT =================
wireForm("form-tarot", "result-tarot", null, async function () {
  const body = {
    spread: $('input[name="tarot-spread"]:checked').value,
    allow_reversed: $("#tarot-allow_reversed").checked,
  };
  const seed = $("#tarot-seed").value;
  if (seed !== "") body.seed = parseInt(seed, 10);
  putOptional(body, "question", $("#tarot-question").value);
  putOptional(body, "focus", $("#tarot-focus").value);
  putOptional(body, "tone", $("#tarot-tone").value);
  putOptional(body, "gender", $("#tarot-gender").value);
  putOptional(body, "context", $("#tarot-context").value);

  const r = await postJSON("/tarot/reading", body);
  if (r.status === 422 || (!r.ok && r.status !== 200)) {
    return [noticeEl("error", "추출 오류: " + detailMessage(r.data))];
  }
  const d = r.data;
  const draw = d.draw;

  const grid = el("div", { class: "tarot-grid" });
  draw.cards.forEach(function (card) {
    const node = el("div", { class: "tarot-card" + (card.reversed ? " reversed" : "") });
    if (card.position) node.appendChild(el("div", { class: "tc-position" }, [card.position]));
    node.appendChild(el("div", { class: "tc-name-ko" }, [card.name_ko]));
    node.appendChild(el("div", { class: "tc-name-en" }, [card.name_en]));
    node.appendChild(el("span", { class: "tc-badge " + (card.reversed ? "rev" : "up") }, [card.reversed ? "역방향" : "정방향"]));
    const kws = el("div", { class: "tc-keywords" });
    (card.keywords || []).forEach(function (k) { kws.appendChild(el("span", { class: "kw-chip" }, [k])); });
    node.appendChild(kws);
    grid.appendChild(node);
  });

  const drawBlock = el("div", { class: "block" }, [
    el("h3", null, ["뽑힌 카드"]),
    grid,
  ]);
  const seedUsed = draw.normalized && draw.normalized.seed_used;
  if (seedUsed != null) {
    drawBlock.appendChild(el("div", { class: "seed-note" }, ["사용된 시드: " + seedUsed + " (같은 시드를 넣으면 동일하게 재현됩니다)"]));
  }

  return [drawBlock, interpretationBlock(d)];
});
