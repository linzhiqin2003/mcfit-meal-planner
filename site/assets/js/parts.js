/* 「拆」页的零件清单：双层吉士汉堡拆成七个零件摊成一排。
 * 进入页面时，零件先叠成一个汉堡，再摊开到各自的格子；切换吃法时零件重新排队，
 * 分到「吃掉 / 留到明早 / 下单去掉」三组，热量数字和下面按热量画的长条跟着变。
 * 每层热量来自 data/ingredient_library.json 里双层吉士汉堡的配方（两片面包只有合计 142，条上各画一半）。
 * 位置全部由这里算：桌面三组横排在一行；窄屏各组的框按内容宽，像文字一样从左往右排，放不下就换行。
 */
(function () {
  "use strict";
  var row = document.getElementById("partsRow");
  if (!row) return;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 叠好时各层的位置：rel 是这层上沿离汉堡顶的距离、h 是层高，单位是切片原图像素；
  // 数字来自 videos/gym-promo/assets/cutouts/burger-v3/stack.json（scripts/bake_burger.py 按实物比例算的），换图后照抄。kcal 用来画长条
  var GEO = {
    "bun-top": { rel: 0, h: 285, kcal: 71 }, "pickles": { rel: 136, h: 140, kcal: 15 },
    "cheese-1": { rel: 162, h: 199, kcal: 45 }, "patty-1": { rel: 160, h: 203, kcal: 91 },
    "cheese-2": { rel: 235, h: 202, kcal: 45 }, "patty-2": { rel: 235, h: 200, kcal: 91 },
    "bun-bottom": { rel: 297, h: 244, kcal: 71 }
  };
  var STACK_H = 541, STACK_W = 723;   // 叠好后的总高、最宽一层的宽（零件图在格子里按 STACK_W 占 94% 缩放）
  // 每种吃法：这一顿的营养（与官方整份营养、配料库求解一致），哪些零件下单去掉、哪些留到明早
  var WAYS = {
    whole: { kcal: 429, p: 27, gone: [], keep: [] },
    nocheese: { kcal: 339, p: 21, gone: ["cheese"], keep: [] },
    filling: { kcal: 272, p: 22, gone: [], keep: ["bread", "sauce"] },
    both: { kcal: 182, p: 16, gone: ["cheese"], keep: ["bread", "sauce"] }
  };
  var GROUPS = [["eat", "吃掉"], ["keep", "留到明早"], ["gone", "下单去掉"]];
  var GAP = 12, PAD = 12, GG = 20, LAB = 52;   // LAB：框下面留给组名和手写批注的高度

  var parts = Array.prototype.map.call(row.querySelectorAll(".pt"), function (el, i) {
    var id = el.getAttribute("data-id");
    el.style.zIndex = String(10 - i);   // 叠成汉堡时上层压住下层
    return { el: el, id: id, k: el.getAttribute("data-k"), i: i, g: GEO[id] };
  });
  var frames = {};
  GROUPS.forEach(function (gr) {
    var f = document.createElement("div");
    f.className = "gp " + gr[0];
    f.innerHTML = '<span class="gl">' + gr[1] + "<b></b>大卡</span>";
    row.appendChild(f);
    frames[gr[0]] = f;
  });
  // 「就吃这个」手写批注放进「吃掉」那组的框里，跟着框移动
  var note = document.getElementById("noteEat");
  if (note) frames.eat.appendChild(note);
  var chips = document.querySelectorAll("#ways [data-way]");
  var sum = document.getElementById("partsSum"), kcalEl = document.getElementById("partsKcal");
  var macro = document.getElementById("partsMacro"), legend = document.getElementById("partsLegend");
  var bar = document.querySelector(".parts-bar");
  var box = document.getElementById("parts"), arrow = document.getElementById("wayArrow");
  var ring = sum.querySelector(".pen-ring"), burst = sum.querySelector(".pen-burst");
  var way = "whole", packed = false, touched = false, timers = [];

  function groupOf(p, w) { return w.gone.indexOf(p.k) >= 0 ? "gone" : w.keep.indexOf(p.k) >= 0 ? "keep" : "eat"; }

  /* ---------- 摆放 ---------- */
  function geom() {
    var W = row.clientWidth, desk = W >= 880;
    var cols = desk ? 7 : W >= 640 ? 6 : W >= 520 ? 4 : 3;
    // 桌面按「三组都在」的最挤情况定格子宽，切吃法时格子不变大小，只换位置
    var cw = desk ? (W - 4 * GAP - 6 * PAD - 2 * GG) / 7 : (W - 2 * PAD - (cols - 1) * GAP) / cols;
    var imH = Math.round(cw * 0.42);   // 最高的一层（顶面包）约占格宽 0.26，上下留一点空
    return { W: W, desk: desk, cols: cols, cw: cw, imH: imH, cellH: imH + 62 };
  }

  function layout() {
    var G = geom(), w = WAYS[way], pos = {}, used = {}, height = 0;
    if (!G.W) return;   // 页面隐藏时量不到宽度，等进入页面再摆
    parts.forEach(function (p) { p.el.style.width = G.cw + "px"; p.el.querySelector(".im").style.height = G.imH + "px"; });
    if (packed) {
      // 叠成一个汉堡：所有零件放在第一格，按叠好时的高度错开
      var u = G.cw * 0.94 / STACK_W, stackH = STACK_H * u, x0 = G.desk ? PAD : (G.W - G.cw) / 2;
      parts.forEach(function (p) {
        pos[p.id] = { x: x0, y: PAD + (G.cellH - stackH) / 2 + (p.g.rel + p.g.h / 2) * u - G.imH / 2 };
      });
      height = PAD * 2 + G.cellH + LAB;
    } else if (way === "whole") {
      // 整份：七个零件按汉堡从上到下的顺序摊成一排（窄屏折行），不画分组框
      // 窄屏折行时各行尽量一样多（6 列的平板排成 4 + 3），每行居中，不剩一个孤零零的底面包
      var gap = G.desk ? (G.W - 7 * G.cw) / 6 : GAP;
      var rows = G.desk ? 1 : Math.ceil(parts.length / G.cols), per = Math.ceil(parts.length / rows);
      parts.forEach(function (p, i) {
        var r = Math.floor(i / per), c = i % per, inRow = Math.min(per, parts.length - r * per);
        var x0 = G.desk ? 0 : (G.W - (inRow * G.cw + (inRow - 1) * gap)) / 2;
        pos[p.id] = { x: x0 + c * (G.cw + gap), y: PAD + r * (G.cellH + GAP) };
      });
      height = PAD * 2 + rows * G.cellH + (rows - 1) * GAP + LAB;
    } else {
      var x = 0, y = 0, lineH = 0;
      GROUPS.forEach(function (gr) {
        var mem = parts.filter(function (p) { return groupOf(p, w) === gr[0]; });
        if (!mem.length) return;
        used[gr[0]] = mem.reduce(function (s, p) { return s + p.g.kcal; }, 0);
        var f = frames[gr[0]], n = mem.length;
        if (G.desk) {
          mem.forEach(function (p, j) { pos[p.id] = { x: x + PAD + j * (G.cw + GAP), y: PAD }; });
          var fw = n * G.cw + (n - 1) * GAP + 2 * PAD;
          place(f, x, 0, fw, G.cellH + 2 * PAD);
          x += fw + GG;
          height = G.cellH + 2 * PAD + LAB;
        } else {
          var per = Math.min(n, G.cols), rws = Math.ceil(n / G.cols);
          var fw2 = per * G.cw + (per - 1) * GAP + 2 * PAD, fh = rws * G.cellH + (rws - 1) * GAP + 2 * PAD;
          if (x > 0 && x + fw2 > G.W) { y += lineH + LAB + 10; x = 0; lineH = 0; }
          var fx = x, fy = y;
          mem.forEach(function (p, j) { pos[p.id] = { x: fx + PAD + (j % G.cols) * (G.cw + GAP), y: fy + PAD + Math.floor(j / G.cols) * (G.cellH + GAP) }; });
          place(f, fx, fy, fw2, fh);
          x += fw2 + GG; lineH = Math.max(lineH, fh);
          height = y + lineH + LAB;
        }
      });
    }
    GROUPS.forEach(function (gr) {
      var on = !packed && used.hasOwnProperty(gr[0]);
      frames[gr[0]].classList.toggle("on", on);
      // 「留到明早」是面包 142 + 酱和酸黄瓜 15；条上两片面包各画 71，标签写合计
      if (on) frames[gr[0]].querySelector("b").textContent = gr[0] === "keep" ? 157 : used[gr[0]];
    });
    parts.forEach(function (p) {
      var q = pos[p.id];
      p.el.style.transform = "translate(" + q.x.toFixed(1) + "px," + q.y.toFixed(1) + "px)";
    });
    row.style.height = Math.ceil(height) + "px";
  }
  /* ---------- 红笔：箭头跟着选中的吃法走；换吃法时重新圈一次数字、重新画箭头 ---------- */
  function ink(svg, delay) {
    if (!svg || reduce || !svg.animate) return;
    var t = delay || 0;
    Array.prototype.forEach.call(svg.querySelectorAll("path"), function (p, i) {
      var d = i ? 140 : (svg === ring ? 560 : 380);
      p.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { duration: d, delay: t, easing: "cubic-bezier(.5,0,.3,1)", fill: "backwards" });
      t += d + (i ? 40 : 60);
    });
  }
  function placeArrow(redraw) {
    var on = document.querySelector('#ways [aria-pressed="true"]');
    if (!arrow || !on || !box.offsetParent) return;
    var pr = box.getBoundingClientRect(), cr = on.getBoundingClientRect();
    arrow.style.left = (cr.right - pr.left + 6).toFixed(1) + "px";
    arrow.style.top = (cr.top - pr.top + cr.height / 2 - 14).toFixed(1) + "px";
    if (redraw) ink(arrow, 120);
  }

  function place(el, x, y, w, h) {
    el.style.left = x + "px"; el.style.top = y + "px"; el.style.width = w + "px"; el.style.height = h + "px";
  }

  /* ---------- 切换吃法 ---------- */
  function setWay(name, opts) {
    opts = opts || {};
    way = name;
    var w = WAYS[name];
    chips.forEach(function (c) { c.setAttribute("aria-pressed", String(c.getAttribute("data-way") === name)); });
    parts.forEach(function (p, i) {
      p.el.classList.toggle("gone", groupOf(p, w) === "gone");
      // 重新排队时从左到右依次出发，像在分拣
      p.el.style.transitionDelay = opts.instant || reduce ? "0ms" : (i * 35) + "ms";
    });
    layout();
    sum.classList.toggle("cut", name !== "whole");
    countTo(w.kcal, opts.instant);
    placeArrow(!opts.instant);
    if (!opts.instant) { ink(ring, 380); ink(burst, 1000); }
    macro.innerHTML = "<span>蛋白质 " + w.p + " g</span>";   // 拆页只说热量和蛋白质（用户要求，不提碳水）
    var eat = w.kcal, keep = w.keep.length ? 157 : 0, gone = w.gone.length ? 90 : 0;
    bar.querySelector(".eat").style.flexGrow = eat;
    bar.querySelector(".keep").style.flexGrow = keep;
    bar.querySelector(".gone").style.flexGrow = gone;
    legend.innerHTML = name === "whole" ? "<span>合计<b>429</b>大卡</span>" :
      "<span>吃掉<b>" + eat + "</b></span>" + (keep ? "<span>留到明早<b>" + keep + "</b></span>" : "") + (gone ? "<span>下单去掉<b>" + gone + "</b></span>" : "");
  }

  var cnt = 0;
  function countTo(n, instant) {
    cancelAnimationFrame(cnt);
    var from = parseInt(kcalEl.textContent, 10) || n;
    if (instant || reduce || from === n) { kcalEl.textContent = n; return; }
    var t0 = performance.now(), d = 650;
    (function step(t) {
      var k = Math.min(1, (t - t0) / d), e = 1 - Math.pow(1 - k, 3);
      kcalEl.textContent = Math.round(from + (n - from) * e);
      if (k < 1) cnt = requestAnimationFrame(step);
    })(t0);
  }

  /* ---------- 进入页面：叠好的汉堡摊开，然后演示一次「去吉士 + 只吃馅」 ---------- */
  function clearTimers() { timers.forEach(clearTimeout); timers = []; }
  function snap(fn) {
    row.classList.add("snap"); fn(); void row.offsetWidth; row.classList.remove("snap");
  }
  function enter() {
    clearTimers();
    touched = false;
    if (reduce) { packed = false; snap(function () { setWay("both", { instant: true }); }); return; }
    packed = true;
    row.classList.add("packed");
    snap(function () { setWay("whole", { instant: true }); });
    timers.push(setTimeout(function () {
      packed = false;
      row.classList.remove("packed");
      parts.forEach(function (p, i) { p.el.style.transitionDelay = (i * 55) + "ms"; });
      layout();
    }, 520));
    timers.push(setTimeout(function () { if (!touched) setWay("both"); }, 2100));
  }

  chips.forEach(function (c) {
    c.addEventListener("click", function () {
      touched = true; clearTimers();
      if (packed) { packed = false; row.classList.remove("packed"); }
      setWay(c.getAttribute("data-way"));
    });
  });
  var rz;
  window.addEventListener("resize", function () {
    cancelAnimationFrame(rz);
    rz = requestAnimationFrame(function () { if (!row.offsetParent) return; snap(layout); placeArrow(false); });
  });
  document.addEventListener("mg:view", function (e) { if (e.detail.name === "拆") requestAnimationFrame(enter); });

  row.classList.add("live");
  // 直接打开 #/拆 时，路由在本脚本加载前就已经切过页了
  if (document.documentElement.getAttribute("data-view") === "拆") requestAnimationFrame(enter);
  else snap(function () { setWay("whole", { instant: true }); });
})();

/* 「怎么算」三行证据图：一行刚进入视口时加 .seen，CSS 让误差须展开、条形长出来、对勾依次出现。
 * 只在元素从视口外进来的那一刻触发，所以看不到「先满、再缩回 0、再长出来」的闪烁；每行只放一次。
 * 区块收在 details 里：收起时这些行不渲染、不会触发，点开后在视口里的行马上触发（这时整块正从透明浮上来，看不到闪烁）。 */
(function () {
  "use strict";
  var rows = document.querySelectorAll(".calc-row");
  if (!rows.length || !("IntersectionObserver" in window)) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.classList.add("seen");
      io.unobserve(e.target);
    });
  }, { threshold: 0 });
  Array.prototype.forEach.call(rows, function (r) { io.observe(r); });
})();

/* 「省钱对比」进入视口时加 .seen：盖上 03 的印章、在拆着吃的价格旁打勾、写「省 ¥4.2」。
 * 和上面一样只在从视口外进来的那一刻触发；没有脚本时这些批注直接是画好的样子。 */
(function () {
  "use strict";
  var vs = document.querySelector(".coach .versus");
  if (!vs || !("IntersectionObserver" in window)) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.classList.add("seen");
      io.unobserve(e.target);
    });
  }, { threshold: 0 });
  io.observe(vs);
})();
