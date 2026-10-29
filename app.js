const DATA = __DATA__;
const YEARS = Object.keys(DATA).map(Number).sort((a, b) => b - a);
const GROUP_KEYS = ["ge", "gk", "me", "mk", "ee", "ek"];
const EK_GROUPS = ["ge", "gk", "ee", "ek"];
const GROUP_NAMES = { ge: "Genel · Erkek", gk: "Genel · Kadın", me: "Milli sporcu · Erkek", mk: "Milli sporcu · Kadın", ee: "Engelli aday · Erkek", ek: "Engelli aday · Kadın" };
const KONT_NAMES = { g: "genel kontenjan", m: "milli sporcu kontenjanı", e: "engelli aday kontenjanı" };
const YER_NAMES = { ilk: "İlk yerleştirme", ek: "Ek yerleştirme" };
const trl = s => (s || "").toLocaleLowerCase("tr-TR");
const collator = new Intl.Collator("tr-TR");
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (n, d = 3) => n == null ? "" : n.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtInt = n => n == null ? "" : n.toLocaleString("tr-TR");

/* ---------- Veri hazırlığı ---------- */
const byKod = {}, grpKeysByYear = {}, HAS_EK = {};
YEARS.forEach(y => {
  byKod[y] = {}; grpKeysByYear[y] = new Set();
  DATA[y].forEach(r => {
    r.year = y;
    r.k2 = [r.uni, r.ptur, r.dil, r.burs].join("|");
    r.grpKey = [r.uni, r.ptur, r.dil].join("|");
    r.text = trl([r.uni, r.sehir, r.fak, r.prog, r.tur === "VAKIF" ? "vakıf" : "devlet"].join(" "));
    byKod[y][r.kod] = r;
    grpKeysByYear[y].add(r.grpKey);
  });
  HAS_EK[y] = DATA[y].some(r => r.x);
});
const prevOf = new Map(), nextOf = new Map();
for (let i = 0; i < YEARS.length - 1; i++) {
  const y = YEARS[i], p = YEARS[i + 1];
  const idx = yr => { const m = {}; DATA[yr].forEach(r => (m[r.k2] = m[r.k2] || []).push(r)); return m; };
  const pK2 = idx(p), yK2 = idx(y);
  DATA[y].forEach(r => {
    let m = byKod[p][r.kod];
    if (!m) {
      const c = pK2[r.k2];
      if (c && c.length === 1 && yK2[r.k2].length === 1 && !byKod[y][c[0].kod]) { m = c[0]; r.kodChanged = true; m.kodChanged = true; }
    }
    if (m) { prevOf.set(r, m); nextOf.set(m, r); }
  });
}
const gv = (r, g, yer) => yer === "ilk" ? r[g] : (r.x ? r.x[g] || null : null);
function agg(rows, g, yer) {
  let k = null, y = null, mn = null, mx = null, any = false;
  rows.forEach(r => {
    const v = gv(r, g, yer);
    if (!v) return;
    any = true;
    if (v[0] != null) k = (k || 0) + v[0];
    if (v[1] != null) y = (y || 0) + v[1];
    if (v[2] != null) mn = mn == null ? v[2] : Math.min(mn, v[2]);
    if (v[3] != null) mx = mx == null ? v[3] : Math.max(mx, v[3]);
  });
  return any ? [k, y, mn, mx] : null;
}
function computeGroups(u) {
  u.g = { ilk: {}, ek: {} };
  GROUP_KEYS.forEach(g => { u.g.ilk[g] = agg(u.rows, g, "ilk"); u.g.ek[g] = agg(u.rows, g, "ek"); });
}
const unitCache = {};
function unitsFor(year, combine) {
  const key = year + "|" + combine;
  if (unitCache[key]) return unitCache[key];
  let units;
  if (!combine) {
    units = DATA[year].map(r => ({ id: r.kod, prevId: prevOf.get(r)?.kod ?? null, rows: [r], label: r.prog, combined: false }));
  } else {
    const m = new Map();
    DATA[year].forEach(r => { if (!m.has(r.grpKey)) m.set(r.grpKey, []); m.get(r.grpKey).push(r); });
    units = [...m.entries()].map(([gk, rows]) => {
      const r0 = rows[0];
      const base = r0.ptur + (r0.dil === "İngilizce" ? " (İngilizce)" : "");
      return { id: gk, prevId: gk, rows, label: rows.length > 1 ? base : r0.prog, combined: rows.length > 1 };
    });
  }
  units.forEach(u => {
    const r0 = u.rows[0];
    Object.assign(u, { year, tur: r0.tur, uni: r0.uni, sehir: r0.sehir, fak: r0.fak, ptur: r0.ptur, dil: r0.dil });
    computeGroups(u);
    u.kodChanged = u.rows.some(r => r.kodChanged);
  });
  unitCache[key] = units;
  return units;
}
function seenEarlier(u, beforeYear) {
  return YEARS.filter(y => y < beforeYear).some(y =>
    S.combine ? grpKeysByYear[y].has(u.rows[0].grpKey) : u.rows.some(r => byKod[y][r.kod]));
}

/* ---------- Durum ---------- */
const S = { year: YEARS[0], yer: "ilk", uni: "", prog: "", tur: "", burs: "", kont: "g", cins: "e", combine: true, unfilled: true, q1: "", q2: "", score: null, onlyOk: false, sort: "min", dir: -1 };
const DEFAULTS = { ...S };

function normalize() {
  if (S.yer === "ek" && !HAS_EK[S.year]) S.yer = "ilk";
  if (S.yer === "ek" && S.kont === "m") S.kont = "g";
  if (S.yer === "ilk" && S.sort === "ilkmin") S.sort = "min";
}
function fillSelects() {
  $("fYear").innerHTML = YEARS.map(y => `<option value="${y}">${y}${HAS_EK[y] ? "" : " (yalnız ilk yerleştirme)"}</option>`).join("");
  const unis = [...new Set(DATA[S.year].map(r => r.uni))].sort(collator.compare);
  if (S.uni && !unis.includes(S.uni)) unis.unshift(S.uni);
  $("fUni").innerHTML = `<option value="">Tümü (${unis.length} üniversite)</option>` + unis.map(u => `<option>${esc(u)}</option>`).join("");
  const progs = [...new Set(YEARS.flatMap(y => DATA[y].map(r => r.ptur)))].sort(collator.compare);
  $("fProg").innerHTML = `<option value="">Tümü</option>` + progs.map(p => {
    const n = DATA[S.year].filter(r => r.ptur === p).length;
    return `<option value="${esc(p)}">${esc(p)}${n ? "" : " (bu yıl yok)"}</option>`;
  }).join("");
  const bursOrder = ["", "Burslu", "%50 İndirimli", "%25 İndirimli", "Ücretli"];
  $("fBurs").innerHTML = `<option value="__all">Tümü</option>` + bursOrder.map(b => `<option value="${b || "__none"}">${b ? b : "Burs/ücret ayrımı yok"}</option>`).join("");
}
function syncControls() {
  $("fYear").value = S.year; $("fUni").value = S.uni; $("fProg").value = S.prog; $("fTur").value = S.tur;
  $("fBurs").value = S.burs === "" ? "__all" : S.burs;
  $("fUnfilled").checked = S.unfilled; $("q1").value = S.q1; $("q2").value = S.q2;
  $("fOnlyOk").disabled = S.score == null; $("fOnlyOk").checked = S.onlyOk && S.score != null;
  [["segYer", S.yer], ["segKont", S.kont], ["segCins", S.cins], ["segComb", S.combine ? "1" : "0"]].forEach(([id, v]) =>
    $(id).querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === v))));
  const ekBtn = $("segYer").querySelector('[data-v="ek"]');
  ekBtn.disabled = !HAS_EK[S.year];
  ekBtn.title = HAS_EK[S.year] ? "" : `${S.year} ek yerleştirme sonuçları henüz eklenmedi`;
  const mBtn = $("segKont").querySelector('[data-v="m"]');
  mBtn.disabled = S.yer === "ek";
  mBtn.title = S.yer === "ek" ? "Ek yerleştirme tablolarında milli sporcu kontenjanı yok" : "";
}

/* ---------- Arama ve liste ---------- */
function parseBox(s) {
  const toks = trl(s).split(/\s+/).filter(Boolean);
  if (!toks.length) return null;
  return toks.map(t => t.startsWith("-") && t.length > 1 ? { neg: true, t: t.slice(1) } : { neg: false, t });
}
function matchBox(text, box) { return box.every(({ neg, t }) => neg ? !text.includes(t) : text.includes(t)); }
const groupKey = () => S.kont + S.cins;
const cur = (u, yer = S.yer) => u.g[yer][groupKey()];

function listFor(year, yer) {
  const g = groupKey();
  const boxes = [parseBox(S.q1), parseBox(S.q2)].filter(Boolean);
  const rowOk = r => (!S.uni || r.uni === S.uni) && (!S.prog || r.ptur === S.prog) && (!S.tur || r.tur === S.tur) &&
    (S.burs === "" || (S.burs === "__none" ? r.burs === "" : r.burs === S.burs));
  let units = unitsFor(year, S.combine).map(u => {
    const rows = u.rows.filter(rowOk);
    if (!rows.length) return null;
    if (rows.length === u.rows.length) return u;
    const v = { ...u, rows, combined: S.combine && rows.length > 1 };
    v.label = rows.length > 1 ? u.label : rows[0].prog;
    computeGroups(v);
    return v;
  }).filter(Boolean);
  units = units.filter(u => {
    const v = u.g[yer][g];
    if (!v) return false;
    const [k, y, mn] = v;
    if (!(k > 0) && !(y > 0)) return false;
    if (!S.unfilled && (y || 0) < (k || 0)) return false;
    if (boxes.length && !boxes.some(b => matchBox(u.rows.map(r => r.text).join(" "), b))) return false;
    if (S.onlyOk && S.score != null && !(mn != null && S.score >= mn)) return false;
    return true;
  });
  const val = u => {
    const [k, y, mn, mx] = u.g[yer][g];
    switch (S.sort) {
      case "min": return mn; case "max": return mx; case "k": return k; case "y": return y;
      case "fill": return k ? (y || 0) / k : null; case "span": return mn != null && mx != null ? mx - mn : null;
      case "ilkmin": return u.g.ilk[g]?.[2] ?? null;
      default: return null;
    }
  };
  units.sort((a, b) => {
    if (S.sort === "uni") return S.dir * (collator.compare(a.uni, b.uni) || collator.compare(a.label, b.label));
    const va = val(a), vb = val(b);
    if (va == null && vb == null) return collator.compare(a.uni, b.uni);
    if (va == null) return 1;
    if (vb == null) return -1;
    if (va === vb) return collator.compare(a.uni, b.uni);
    return S.dir === -1 ? vb - va : va - vb;
  });
  return units;
}

/* ---------- Çizim ---------- */
function columns() {
  const ek = S.yer === "ek";
  const cols = [
    { key: null, label: "Sıra" },
    { key: "uni", label: "Üniversite" },
    { key: null, label: "Program" },
    { key: "k", label: ek ? "Ek kontenjan" : "Kontenjan", cls: "num" },
    { key: "y", label: "Yerleşen", cls: "num" },
    { key: "fill", label: "Doluluk", cls: "num" },
    { key: "min", label: "En küçük puan", cls: "num" },
    { key: "max", label: "En büyük puan", cls: "num" },
  ];
  if (ek) cols.push({ key: "ilkmin", label: "İlk yerl. en küçük", cls: "num" });
  cols.push({ key: "span", label: "Puan aralığı" });
  if (S.score != null) cols.push({ key: null, label: "Puanınız" });
  return cols;
}
function renderHead(cols) {
  $("thead").innerHTML = cols.map(c => {
    const cls = c.cls || "";
    if (!c.key) return `<th class="${cls}" scope="col">${c.label}</th>`;
    const act = S.sort === c.key;
    const arrow = act ? (S.dir === -1 ? " ↓" : " ↑") : "";
    return `<th class="${cls}" scope="col" aria-sort="${act ? (S.dir === -1 ? "descending" : "ascending") : "none"}"><button class="sort" type="button" data-sort="${c.key}" ${act ? "data-active" : ""}>${c.label}${arrow}</button></th>`;
  }).join("");
}
function chg(d, digits, title = "") {
  if (d == null) return "";
  const t = title ? ` title="${title}"` : "";
  if (Math.abs(d) < 1e-9) return `<span class="delta chg same"${t}>● 0</span>`;
  const s = (d > 0 ? "+" : "−") + (digits ? fmt(Math.abs(d), digits) : fmtInt(Math.abs(d)));
  return `<span class="delta chg ${d > 0 ? "up" : "down"}"${t}>${d > 0 ? "▲" : "▼"} ${s}</span>`;
}
function render() {
  normalize();
  const g = groupKey(), yer = S.yer, isEk = yer === "ek";
  const list = listFor(S.year, yer);
  const yi = YEARS.indexOf(S.year);
  let prevYear = yi < YEARS.length - 1 ? YEARS[yi + 1] : null;
  if (prevYear && isEk && !HAS_EK[prevYear]) prevYear = null;
  let prevRank = null, prevAll = null;
  if (prevYear) {
    prevRank = new Map(listFor(prevYear, yer).map((u, i) => [u.id, i]));
    prevAll = new Map(unitsFor(prevYear, S.combine).map(u => [u.id, u]));
  }
  const mins = list.map(u => cur(u)[2]).filter(v => v != null), maxs = list.map(u => cur(u)[3]).filter(v => v != null);
  const lo = mins.length ? Math.floor(Math.min(...mins) / 10) * 10 : 0, hi = maxs.length ? Math.ceil(Math.max(...maxs) / 10) * 10 : 1;
  const pct = v => ((v - lo) / Math.max(1, hi - lo)) * 100;
  const cols = columns();
  renderHead(cols);

  let sk = 0, sy = 0, unf = 0, ok = 0;
  list.forEach(u => { const [k, y, mn] = cur(u); sk += k || 0; sy += y || 0; if ((y || 0) < (k || 0)) unf++; if (S.score != null && mn != null && S.score >= mn) ok++; });
  $("summary").innerHTML = [
    [fmtInt(list.length), "program listelendi"],
    [fmtInt(sk), isEk ? "ek kontenjan" : "kontenjan"],
    [fmtInt(sy), isEk ? "ek yerleştirmede yerleşen" : "yerleşen"],
    [fmtInt(unf), "kontenjanı dolmayan program"],
    ...(S.score != null ? [[fmtInt(ok), `programda ${fmt(S.score, 2)} puan en küçük puana yetiyor`]] : []),
  ].map(([b, s]) => `<div><b>${b}</b><span>${s}</span></div>`).join("");
  $("ctxTitle").textContent = `${S.year} · ${YER_NAMES[yer]} · ${GROUP_NAMES[g]}`;
  const parts = [];
  if (isEk) {
    parts.push(prevYear ? `Ek kontenjan değişimi ${prevYear} ek yerleştirmesine göre.` : "Önceki yılın ek yerleştirme verisi olmadığından kontenjan değişimi gösterilmiyor.");
    parts.push("En küçük puandaki fark aynı yılın ilk yerleştirmesine göre.");
  } else {
    parts.push(prevYear ? `Sıra, kontenjan ve en küçük puan değişimi ${prevYear} yılına göre.` : "Önceki yıl verisi yok, değişim gösterilmiyor.");
  }
  $("ctxHint").textContent = parts.join(" ");

  if (!list.length) {
    $("tbody").innerHTML = `<tr><td colspan="${cols.length}"><div class="empty">Bu filtrelere uyan program yok. Kontenjan grubunu değiştirmeyi veya filtreleri temizlemeyi deneyin.</div></td></tr>`;
    window.__list = list;
    return;
  }
  $("tbody").innerHTML = list.map((u, i) => {
    const [k, y, mn, mx] = cur(u);
    const unfilled = (y || 0) < (k || 0);
    let rankMark = "", dk = null, dmin = null, dminTitle = "";
    if (prevYear) {
      const pu = prevAll.get(u.prevId);
      const pv = pu ? pu.g[yer][g] : null;
      if (!pu) {
        if (!isEk) rankMark = seenEarlier(u, prevYear)
          ? `<span class="chg same" title="${prevYear} tablosunda yok, daha önceki bir yılda vardı">DÖNDÜ</span>`
          : `<span class="chg new" title="Önceki yılların tablolarında karşılığı yok">YENİ</span>`;
      } else {
        if (k != null) dk = k - ((pv && pv[0]) || 0);
        if (!isEk && mn != null && pv && pv[2] != null) { dmin = mn - pv[2]; dminTitle = `${prevYear} en küçük puana göre`; }
        if (!isEk && prevRank.has(u.prevId)) {
          const d = prevRank.get(u.prevId) - i;
          rankMark = d > 0 ? `<span class="chg up" title="${d} sıra yükseldi">▲${d}</span>` : d < 0 ? `<span class="chg down" title="${-d} sıra düştü">▼${-d}</span>` : `<span class="chg same" title="Sırası değişmedi">●</span>`;
        }
      }
    }
    const ilkMin = u.g.ilk[g]?.[2] ?? null;
    if (isEk && mn != null && ilkMin != null) { dmin = mn - ilkMin; dminTitle = "Aynı yılın ilk yerleştirmesine göre"; }
    const tags = (u.combined ? `<span class="tag" title="Burslu ve ücretli seçenekler birleştirildi">BB</span>` : "") + (u.kodChanged ? `<span class="tag kod" title="ÖSYM kodu yıllar arasında değişti">kod değişti</span>` : "");
    const range = mn != null && mx != null ? `<div class="range" title="${fmt(mn, 2)} – ${fmt(mx, 2)}"><i style="left:${pct(mn).toFixed(2)}%;width:${Math.max(1.5, pct(mx) - pct(mn)).toFixed(2)}%"></i></div>` : `<span class="dash">yerleşen yok</span>`;
    let scoreCell = "";
    if (S.score != null) {
      scoreCell = mn == null ? `<td><span class="pill na">Yerleşen yok</span></td>` : S.score >= mn ? `<td><span class="pill ok">Yeterdi</span></td>` : `<td><span class="pill no">${fmt(mn - S.score, 2)} eksik</span></td>`;
    }
    const sub = [u.sehir, u.tur === "VAKIF" ? "Vakıf" : "Devlet"].filter(Boolean).join(" · ");
    return `<tr class="${unfilled ? "unfilled" : ""}">
      <td><div class="rank"><span class="n">${i + 1}</span>${rankMark}</div></td>
      <td class="uni"><button type="button" data-uni="${esc(u.uni)}" class="${u.tur === "DEVLET" ? "devlet" : ""}" title="Yalnızca bu üniversiteyi göster">${esc(u.uni)}</button><span class="sub">${esc(sub)}</span></td>
      <td class="prog"><button class="open" type="button" data-open="${esc(u.id)}">${esc(u.label)}</button>${tags}<span class="sub">${esc(u.fak)}${!u.combined ? " · " + u.rows[0].kod : ""}</span></td>
      <td class="num">${fmtInt(k ?? 0)}${chg(dk, 0, prevYear ? `${prevYear} yılına göre` : "")}</td>
      <td class="num">${fmtInt(y ?? 0)}</td>
      <td class="num">${k ? Math.round(((y || 0) / k) * 100) + "%" : '<span class="dash">–</span>'}</td>
      <td class="num"><span class="score">${mn != null ? fmt(mn) : '<span class="dash">–</span>'}</span>${chg(dmin, 2, dminTitle)}</td>
      <td class="num">${mx != null ? fmt(mx) : '<span class="dash">–</span>'}</td>
      ${isEk ? `<td class="num">${ilkMin != null ? fmt(ilkMin) : '<span class="dash">–</span>'}</td>` : ""}
      <td>${range}</td>${scoreCell}
    </tr>`;
  }).join("");
  window.__list = list;
}

/* ---------- Program detayı ---------- */
function chainOf(r) {
  const out = {}; let c = r;
  while (c) { out[c.year] = c; c = nextOf.get(c); }
  c = prevOf.get(r);
  while (c) { out[c.year] = c; c = prevOf.get(c); }
  // Ara yıl eksikse (ör. 2025'te olmayan program) aynı kodla daha eski yıllara bak
  YEARS.forEach(y => { if (!out[y] && byKod[y][r.kod]) out[y] = byKod[y][r.kod]; });
  return out;
}
function detailTable(ch, yrs, groups, yer) {
  const head1 = `<tr class="grp-head"><th rowspan="2" scope="col">Kontenjan grubu</th>${yrs.map(y => `<th colspan="4" scope="colgroup">${y}</th>`).join("")}<th class="bl" rowspan="2" scope="col">En küçük puan farkı</th></tr>`;
  const head2 = `<tr>${yrs.map(() => `<th class="num bl">Kont.</th><th class="num">Yerl.</th><th class="num">En küçük</th><th class="num">En büyük</th>`).join("")}</tr>`;
  const body = groups.map(g => {
    const cells = yrs.map(y => {
      const v = ch[y] ? gv(ch[y], g, yer) : null;
      if (!v) return `<td class="bl dash" colspan="4">${ch[y] ? "–" : "tabloda yok"}</td>`;
      return `<td class="num bl">${v[0] ?? "–"}</td><td class="num">${v[1] ?? "–"}</td><td class="num">${v[2] != null ? fmt(v[2], 5) : "–"}</td><td class="num">${v[3] != null ? fmt(v[3], 5) : "–"}</td>`;
    }).join("");
    const withMin = yrs.filter(y => ch[y] && gv(ch[y], g, yer)?.[2] != null);
    let d = null, title = "";
    if (withMin.length >= 2) {
      const a = withMin[withMin.length - 2], b = withMin[withMin.length - 1];
      d = gv(ch[b], g, yer)[2] - gv(ch[a], g, yer)[2]; title = `${b} − ${a}`;
    }
    const strong = g === groupKey() ? ' style="font-weight:700"' : "";
    return `<tr${strong}><th scope="row">${GROUP_NAMES[g]}</th>${cells}<td class="num bl">${d != null ? chg(d, 2, title).replace('class="delta', 'class="') + `<span class="sub" style="display:block;font-size:11px;color:var(--muted)">${title}</span>` : '<span class="dash">–</span>'}</td></tr>`;
  }).join("");
  return `<div class="dtable"><table><thead>${head1}${head2}</thead><tbody>${body}</tbody></table></div>`;
}
function openDetail(id) {
  const u = (window.__list || []).find(x => x.id === id);
  if (!u) return;
  $("dTitle").textContent = `${u.uni} · ${u.label}`;
  $("dSub").textContent = [u.fak, u.sehir, u.tur === "VAKIF" ? "Vakıf üniversitesi" : "Devlet üniversitesi"].filter(Boolean).join(" · ");
  const yrs = [...YEARS].sort((a, b) => a - b);
  const ekYrs = yrs.filter(y => HAS_EK[y]);
  $("dBody").innerHTML = u.rows.map(r => {
    const ch = chainOf(r);
    const codes = yrs.map(y => ch[y] ? `${y}: ${ch[y].kod}` : `${y}: tabloda yok`).join(" · ");
    return `<section style="display:grid;gap:10px;min-width:0"><div><h4>${esc(r.prog)}</h4><p class="hint" style="margin:0">ÖSYM kodu ${codes}${r.kodChanged ? " (kod değişti)" : ""}</p></div>
      <div style="min-width:0"><h4 style="font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em">İlk yerleştirme</h4>${detailTable(ch, yrs, GROUP_KEYS, "ilk")}</div>
      ${ekYrs.length ? `<div style="min-width:0"><h4 style="font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em">Ek yerleştirme</h4>${detailTable(ch, ekYrs, EK_GROUPS, "ek")}</div>` : ""}
    </section>`;
  }).join("");
  showOverlay("ovDetail");
}

/* ---------- Katman yönetimi ---------- */
let lastFocus = null;
function showOverlay(id) { lastFocus = document.activeElement; $(id).hidden = false; $(id).querySelector("[data-close]").focus(); }
function hideOverlays() { ["ovDetail", "ovHelp"].forEach(id => $(id).hidden = true); if (lastFocus) lastFocus.focus(); }
document.querySelectorAll(".overlay").forEach(o => o.addEventListener("click", e => { if (e.target === o || e.target.closest("[data-close]")) hideOverlays(); }));
document.addEventListener("keydown", e => { if (e.key === "Escape") hideOverlays(); });
document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".tabs button").forEach(x => x.setAttribute("aria-selected", String(x === b)));
  document.querySelectorAll("[data-pane]").forEach(p => p.hidden = p.dataset.pane !== b.dataset.tab);
}));
$("btnHelp").addEventListener("click", () => showOverlay("ovHelp"));

/* ---------- Olaylar ---------- */
function update(patch, refill) { Object.assign(S, patch); normalize(); if (refill) fillSelects(); syncControls(); render(); }
$("fYear").addEventListener("change", e => update({ year: Number(e.target.value) }, true));
$("fUni").addEventListener("change", e => update({ uni: e.target.value }));
$("fProg").addEventListener("change", e => update({ prog: e.target.value }));
$("fTur").addEventListener("change", e => update({ tur: e.target.value }));
$("fBurs").addEventListener("change", e => update({ burs: e.target.value === "__all" ? "" : e.target.value }));
$("fUnfilled").addEventListener("change", e => update({ unfilled: e.target.checked }));
$("fOnlyOk").addEventListener("change", e => update({ onlyOk: e.target.checked }));
let qt;
["q1", "q2"].forEach(id => $(id).addEventListener("input", e => { clearTimeout(qt); qt = setTimeout(() => update({ [id]: e.target.value }), 150); }));
$("fScore").addEventListener("input", e => {
  clearTimeout(qt);
  qt = setTimeout(() => {
    const v = parseFloat(e.target.value.replace(/\s/g, "").replace(",", "."));
    const okv = Number.isFinite(v) && v > 0;
    update({ score: okv ? v : null, onlyOk: okv ? S.onlyOk : false });
  }, 200);
});
const segHandler = (id, fn) => $(id).addEventListener("click", e => { const b = e.target.closest("button"); if (b && !b.disabled) update(fn(b.dataset.v)); });
segHandler("segYer", v => ({ yer: v }));
segHandler("segKont", v => ({ kont: v }));
segHandler("segCins", v => ({ cins: v }));
segHandler("segComb", v => ({ combine: v === "1" }));
$("thead").addEventListener("click", e => {
  const b = e.target.closest("[data-sort]"); if (!b) return;
  const k = b.dataset.sort;
  update(S.sort === k ? { dir: -S.dir } : { sort: k, dir: k === "uni" ? 1 : -1 });
});
$("tbody").addEventListener("click", e => {
  const o = e.target.closest("[data-open]"); if (o) return openDetail(o.dataset.open);
  const u = e.target.closest("[data-uni]"); if (u) update({ uni: u.dataset.uni });
});
$("btnReset").addEventListener("click", () => { $("fScore").value = ""; update({ ...DEFAULTS }, true); });

fillSelects(); syncControls(); render();
