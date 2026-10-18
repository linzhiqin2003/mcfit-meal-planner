/* Gyᗰ 麦门健身房 · 生成器和训练日志
 * 数据：data/plans.json，由 scripts/build_site_data.py 用门店快照离线算出（热量上限 × 蛋白质下限 × 训练部位）。
 * 状态改动统一走 MG.set()，再派发 mg:state 事件；首屏小人（home.js）等模块可以监听这个事件。
 */
(function () {
  "use strict";

  var PARTS = {
    "练腿": { tag: "LEG DAY", icon: "i-leg", motto: "Never skip leg day，鸡腿日更不能跳" },
    "练胸": { tag: "CHEST DAY", icon: "i-nugget", motto: "周一练胸是健身房的国际惯例" },
    "练手臂": { tag: "ARM DAY", icon: "i-arm", motto: "麒麟臂从鸡翅开始" },
    "练背": { tag: "BACK DAY", icon: "i-back", motto: "背练出来自己看不见，里脊吃下去自己知道" },
    "": { tag: "ANY DAY", icon: "i-any", motto: "今天不挑部位，只挑最便宜的" }
  };
  var CHIPS = ["练腿", "练胸", "练背", "练手臂", ""];
  var KCAL = [400, 500, 600, 700, 800], PROTEIN = [20, 30, 40];
  var STORE = "麦当劳上海福州路餐厅";

  var state = { kcal: 500, protein: 30, train: "练腿", rank: 0 };
  var data = null;

  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function use(id) { return '<svg class="i"><use href="#' + id + '"/></svg>'; }
  function g(x) { return Math.round(x); }
  function money(x) { return "¥" + Number(x).toFixed(1); }
  function sep(items) { return '<div class="s' + (items.length > 1 ? " sep" : "") + '">' + items.map(function (t) { return "<span>" + esc(t) + "</span>"; }).join("") + "</div>"; }
  function iconOf(name) {
    if (/鸡腿|琵琶腿/.test(name)) return "i-leg";
    if (/麦乐鸡|鸡块|鸡柳/.test(name)) return "i-nugget";
    if (/翅/.test(name)) return "i-wing";
    if (/里脊/.test(name)) return "i-back";
    if (/奶|豆浆/.test(name)) return "i-milk";
    return "i-burger";
  }
  function perSet(s) { var m = /(\d+)\s*(\S+?)一组/.exec(s || ""); return m ? [m[1], m[2]] : ["1", "个"]; }
  function isCut(how) { return /只吃馅|去/.test(how || ""); }
  function key(st) { return st.kcal + "|" + st.protein + "|" + st.train; }
  function result(st) { return data && data.plans[key(st)]; }

  /* ---------- 训练单（「练」页） ---------- */
  function renderLog() {
    var part = PARTS[state.train], r = result(state);
    $("logTag").innerHTML = "TODAY · <em>" + part.tag + "</em>";
    $("logIcon").innerHTML = '<use href="#' + part.icon + '"/>';
    $("logTitle").textContent = "今日训练：" + (state.train || "不限部位");
    $("logMotto").textContent = part.motto;
    $("logStore").textContent = STORE + " · " + state.kcal + " 大卡 · 蛋白质 " + state.protein + " 克";
    var body = "", sc = $("logScore");
    var p = r && r.ok && r.plans[state.rank];
    if (!p) {
      var msg = (r && r.message) || "这个组合还没算过，换一组条件试试。";
      body = '<tr class="empty"><td colspan="5"><div class="empty-line">' + use("i-ban") + "<span>" + esc(msg) + "</span></div></td></tr>";
      sc.style.display = "none";
    } else {
      p.rows.forEach(function (row, i) {
        var q = perSet(row.per_set);
        var how = row.how ? '<td class="how' + (isCut(row.how) ? " cut" : "") + '">' + esc(row.how) + "</td>" : '<td class="how none">—</td>';
        body += '<tr class="row"><td class="no">' + (i < 9 ? "0" : "") + (i + 1) + '</td><td><div class="act">' + use(iconOf(row.name)) + esc(row.name) + "</div></td>" +
          '<td class="qty"><b>' + q[0] + "</b><span>" + esc(q[1]) + '</span></td><td class="qty"><b>' + row.sets + "</b><span>组</span></td>" + how + "</tr>";
      });
      var tip = p.tip ? '<span class="k">动作要领</span>' + esc(p.tip) : "";
      if (p.estimated) tip += '<span class="est">含估算营养</span>';
      if (tip) body += '<tr class="tip"><td colspan="5">' + tip + "</td></tr>";
      var t = p.this_meal, n = p.next_meal, cells = [
        '<div><div class="k">训练量</div><div class="v"><b>' + g(t.kcal) + "</b><span>大卡</span></div>" + sep(["碳水 " + g(t.carb_g) + " g", "脂肪 " + g(t.fat_g) + " g"]) + "</div>",
        // data-ok：这一顿蛋白质够不够目标，train-pen.js 据此在旁边打勾写「达标」
        '<div class="protein" data-ok="' + (t.protein_g >= state.protein ? 1 : 0) + '"><div class="k">蛋白质</div><div class="v"><b>' + g(t.protein_g) + "</b><span>g</span></div>" + sep(["目标 " + state.protein + " 克"]) + "</div>",
        '<div class="price"><div class="k">会员费</div><div class="v"><b>' + money(p.price) + "</b></div>" + sep(["方案 " + (state.rank + 1)]) + "</div>"
      ];
      if (n && n.kcal > 0) cells.push('<div><div class="k">明早拉伸</div><div class="v"><b>' + g(n.kcal) + "</b><span>大卡</span></div>" + sep(["蛋白质 " + g(n.protein_g) + " g", "碳水 " + g(n.carb_g) + " g", "脂肪 " + g(n.fat_g) + " g"]) + "</div>");
      sc.style.display = "";
      sc.className = "score" + (cells.length === 3 ? " c3" : "");
      sc.innerHTML = cells.join("");
    }
    $("logBody").innerHTML = body;
    $("logTable").classList.toggle("is-empty", !p);
    // 训练单最后一节：到店怎么点（套餐名照官方菜单写，括号里是要备注的改动）
    var od = $("logOrder");
    od.hidden = !p;
    od.innerHTML = p ? '<span class="k">怎么下单</span><div><ul class="order">' + p.order_lines.map(function (l) {
      var m = /^(\d+\s*×)\s*(.*)$/.exec(l) || [null, "", l];
      return '<li><span class="x">' + esc(m[1]) + "</span><span>" + esc(m[2]) + "</span></li>";
    }).join("") + "</ul>" + (p.footnotes && p.footnotes.length ? '<p class="note">' + p.footnotes.map(esc).join("<br>") + "</p>" : "") + "</div>" : "";
  }

  /* ---------- 生成器：参数 + 方案列表（所选方案的详情就是上面的训练单） ---------- */
  function renderGenerator() {
    document.querySelector('[data-field="kcal"] output').textContent = state.kcal;
    document.querySelector('[data-field="protein"] output').textContent = state.protein;
    $("chips").innerHTML = CHIPS.map(function (c) {
      return '<button class="chip" type="button" data-part="' + c + '" aria-pressed="' + (state.train === c) + '">' + (c || "不限") + "</button>";
    }).join("");
    var r = result(state);
    if (!r || !r.ok || !r.plans.length) {
      $("ranks").innerHTML = '<li class="none">' + esc((r && r.message) || "这个组合还没算过，换一组条件试试。") + "</li>";
      return;
    }
    $("ranks").innerHTML = r.plans.map(function (p, i) {
      var names = p.rows.map(function (row) { return '<span class="nw">' + esc(row.name) + "</span>" + (row.how ? "（" + esc(row.how) + "）" : ""); }).join(" + ");
      return '<li class="' + (i === state.rank ? "on" : "") + '" data-rank="' + i + '" tabindex="0" aria-current="' + (i === state.rank) + '"><div class="pos">方案 ' + (i + 1) + "</div><b>" + money(p.price) + "</b><p>" + names + "</p>" +
        '<div class="st sep"><span>' + g(p.this_meal.kcal) + " 大卡</span><span>蛋白质 " + g(p.this_meal.protein_g) + " g</span><span>碳水 " + g(p.this_meal.carb_g) + " g</span></div></li>";
    }).join("");
  }

  function renderAll() { renderLog(); renderGenerator(); }

  function set(patch, opts) {
    var prevTrain = state.train;
    Object.keys(patch).forEach(function (k) { state[k] = patch[k]; });
    if (!("rank" in patch)) state.rank = 0;
    renderAll();
    document.dispatchEvent(new CustomEvent("mg:state", { detail: { state: Object.assign({}, state), trainChanged: prevTrain !== state.train, source: (opts && opts.source) || "" } }));
  }

  /* ---------- 交互 ---------- */
  function step(field, dir) {
    var list = field === "kcal" ? KCAL : PROTEIN, i = list.indexOf(state[field]) + dir;
    if (i < 0 || i >= list.length) return;
    var patch = {}; patch[field] = list[i]; set(patch, { source: "params" });
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-step]");
    if (t) return step(t.closest("[data-field]").getAttribute("data-field"), +t.getAttribute("data-step"));
    t = e.target.closest(".chip[data-part]");
    if (t) return set({ train: t.getAttribute("data-part") }, { source: "chips" });
    t = e.target.closest(".ranks li[data-rank]");
    if (t) return set({ rank: +t.getAttribute("data-rank") }, { source: "ranks" });
    if (e.target.closest("#copyBtn")) copyInstall();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var t = e.target.closest(".ranks li[data-rank]");
    if (!t) return;
    e.preventDefault();
    t.click();
  });

  function copyInstall() {
    var text = $("cloneCmd").textContent + "\ncd maimen-gym && python3 install.py --target workbuddy";
    var btn = $("copyBtn");
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () {
      btn.innerHTML = use("i-check"); btn.setAttribute("aria-label", "已复制");
      setTimeout(function () { btn.innerHTML = use("i-copy"); btn.setAttribute("aria-label", "复制命令"); }, 1600);
    }, function () { /* 不支持剪贴板时什么也不做，命令仍可手动选中 */ });
  }

  window.MG = { set: set, get: function () { return Object.assign({}, state); }, parts: PARTS };

  fetch("data/plans.json").then(function (r) {
    if (!r.ok) throw new Error("plans.json " + r.status);
    return r.json();
  }).then(function (d) {
    data = d;
    renderAll();
    document.dispatchEvent(new CustomEvent("mg:ready", { detail: { state: Object.assign({}, state) } }));
  }).catch(function (err) {
    // 数据没加载到时保留首屏写死的默认方案，只把交互区换成提示
    console.warn("[maimen-gym] 方案数据加载失败", err);
    $("ranks").innerHTML = '<li class="none">方案数据暂时加载不出来，刷新一下试试。</li>';
  });
})();
