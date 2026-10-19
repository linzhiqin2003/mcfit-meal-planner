/* 首屏三个入口小人（A 方向：和大标题互动）。
 *   鸡腿吊在第一个「to」的 t 上：双手在横杠后面（只露指节），身体在字前面 → 练
 *   麦乐鸡坐在「Gym」的 m 上（屁股底边对准 x 高度）→ 装
 *   汉堡站在金色 ᗰ 的右后方：身体在 ᗰ 后面，左手绕过来扒住 ᗰ 的右边缘（拳头在 ᗰ 前面）→ 拆
 * 位置按字母的实际几何算：基线用零尺寸的行内标记取，x 高度用 canvas 量字体；窗口变化、字体加载后重算。
 * 行为：眼睛跟随鼠标（久不动就自己东张西望）、随机眨眼；鸡腿轻荡并不时做个引体向上，麦乐鸡晃腿似的轻摇，
 * 汉堡偶尔拽一下 ᗰ 再推回去（ᗰ 跟着手一起晃）；悬停眯眼笑、标签点亮；点一下蹦一下并进入对应的信息页。
 */
(function () {
  "use strict";
  var stage = document.getElementById("stage"), crew = document.getElementById("crew2"), mega = document.getElementById("mega");
  if (!stage || !crew || !mega) return;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 各小人的高度（以大标题字号 em 计）和入口信息
  var CAST = [
    // arrow：标签旁的手绘箭头指向小人身体的哪一侧边缘（L/R）、在图高百分之几处，bow 是弧度（正负决定往哪边鼓）
    { pose: "drumstick-hang", page: "练", h: 1.02, label: "练", desc: "生成训练计划", side: "left", arrow: { edge: "L", row: 50, bow: 0.28 } },
    { pose: "nugget-sit", page: "装", h: 0.98, label: "装", desc: "装到 WorkBuddy", side: "right", arrow: { edge: "R", row: 40, bow: 0.3 } },
    { pose: "burger-side", page: "拆", label: "拆", desc: "只吃馅怎么算", side: "right", arrow: { edge: "R", row: 40, bow: -0.3 } }
  ];
  var ORDER = ["练", "拆", "装"];
  // 鸡腿的拳头在姿势图里的上下沿（图高 %）；拳头露出横杠上沿的比例。h=1.02em 时两只拳头的外沿刚好落在横杠两端以内
  var GRIP = { top: 0.8, bottom: 8.6, peek: 0.45 };
  // 汉堡扒住 ᗰ 的位置：ᗰ 图高 30% 处（偏上，汉堡站在底线上时比 ᗰ 略高），那一行最右竖笔的外沿在图宽 96.1%
  // rim：ᗰ 外沿那圈金边的宽度（ᗰ 图宽的比例）。手指根部落在金边下面被压住，只露出弯到正面的指尖
  var GOLD_GRIP = { edge: 0.961, y: 0.3, rim: 0.035 };
  var back = null;
  var poses = null, cast = [], pointer = null, lastMove = 0;

  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html) e.innerHTML = html; return e; }

  function build() {
    crew.innerHTML = "";
    // 文字后面的一层：只放鸡腿的双手，让 t 的横杠压在手上
    back = document.getElementById("crewBack") || el("div", "crew-back");
    back.id = "crewBack"; back.setAttribute("aria-hidden", "true"); back.innerHTML = "";
    if (!back.parentNode) stage.insertBefore(back, mega);
    cast = CAST.map(function (c) {
      var m = poses[c.pose];
      var b = el("a", "hb hb-" + c.pose);
      b.href = "#/" + c.page;
      b.setAttribute("data-go", c.page);
      b.setAttribute("data-page", c.page);
      b.setAttribute("aria-label", c.label + "：" + c.desc);
      var body = el("span", "hb-body");
      var img = el("img"); img.src = "assets/img/pose-" + c.pose + ".webp"; img.alt = ""; img.draggable = false;
      body.appendChild(img);
      var eyes = [m.l, m.r].map(function (p) { var e = el("i", "eye"); e.style.left = p[0] + "%"; e.style.top = p[1] + "%"; body.appendChild(e); return e; });
      b.appendChild(body);
      crew.appendChild(b);
      var pill = el("a", "pill pill-" + c.side, '<b>' + c.label + "</b><span>" + c.desc + '</span><svg class="i"><use href="#i-arrow"/></svg>');
      pill.href = "#/" + c.page; pill.setAttribute("data-go", c.page); pill.setAttribute("tabindex", "-1"); pill.setAttribute("aria-hidden", "true");
      crew.appendChild(pill);
      var arrow = c.arrow ? mkArrow() : null;
      if (arrow) crew.appendChild(arrow);
      var o = { c: c, m: m, a: b, body: body, img: img, eyes: eyes, pill: pill, arrow: arrow, lean: 0 };
      if (c.pose === "drumstick-hang" || c.pose === "burger-side") {
        // 同一张图再放一份到文字后面：鸡腿那份只显示双手（压在 t 的横杠下），汉堡那份显示除拳头外的全身（藏在 ᗰ 后面）。
        // 两份用同一套摆动和动画，接缝不会错开
        o.twin = el("span", "hb hb-" + c.pose + " hb-twin");
        o.twinBody = el("span", "hb-body");
        var ti = el("img"); ti.src = img.src; ti.alt = ""; ti.draggable = false;
        o.twinBody.appendChild(ti); o.twin.appendChild(o.twinBody);
        if (c.pose === "burger-side") {
          // 汉堡身体只该被 ᗰ 挡住，不该被第一行「Gym」的 y 挡住：身体、一张与 ᗰ 完全重合的副本、拳头三层都放在前面这组里
          var gold = document.getElementById("ank-gold");
          o.cover = el("img", "gm-cover"); o.cover.src = gold.currentSrc || gold.src; o.cover.alt = ""; o.cover.setAttribute("aria-hidden", "true");
          crew.appendChild(o.twin); crew.appendChild(o.cover);
        } else back.appendChild(o.twin);
      }
      b.addEventListener("pointerenter", function () { hover(o, true); });
      b.addEventListener("pointerleave", function () { hover(o, false); });
      pill.addEventListener("pointerenter", function () { hover(o, true); });
      pill.addEventListener("pointerleave", function () { hover(o, false); });
      b.addEventListener("focus", function () { hover(o, true); });
      b.addEventListener("blur", function () { hover(o, false); });
      b.addEventListener("click", function () { hop(o); });
      return o;
    });
    layout();
    cast.forEach(blinkLoop);
    if (!reduce) cast.forEach(idleLoop);
    requestAnimationFrame(tick);
    stage.classList.add("ready");
  }

  /* ---------- 几何：字母的位置 ---------- */
  var probeCanvas = document.createElement("canvas").getContext("2d");
  function fontMetrics() {
    var cs = getComputedStyle(mega), size = parseFloat(cs.fontSize);
    // canvas 的 font 简写不认「75%」这类字宽，写进去整条作废、退回 10px sans-serif；字宽单独设
    probeCanvas.font = cs.fontStyle + " " + cs.fontWeight + " " + cs.fontSize + " " + cs.fontFamily;
    if ("fontStretch" in probeCanvas) probeCanvas.fontStretch = "condensed";
    var x = probeCanvas.measureText("x").actualBoundingBoxAscent;
    if (!(x > size * 0.3 && x < size * 0.8)) x = size * 0.52;   // 量不出来（或量到了兜底字体）时按常见 x 高度估
    return { size: size, xh: x };
  }
  function baselineOf(span) {
    var mk = span.querySelector(".bl");
    if (!mk) { mk = el("i", "bl"); span.appendChild(mk); }
    return mk.getBoundingClientRect().bottom;
  }
  // t 的横杠：在 canvas 上画一个 t，逐行扫描，从顶上往下第一段比竖笔明显宽的连续行就是横杠。
  // 返回相对基线的上下沿、相对字形起点的左右端（px）；量不出来返回 null，退回按 x 高度估
  var barCache = {};
  function crossbar(cs, size) {
    var key = cs.fontFamily + "|" + cs.fontWeight + "|" + size;
    if (barCache.hasOwnProperty(key)) return barCache[key];
    var S = Math.ceil(size * 1.4), cv = document.createElement("canvas"); cv.width = cv.height = S;
    var g = cv.getContext("2d"), ox = Math.round(size * 0.2), by = Math.round(size * 1.1);
    g.font = cs.fontStyle + " " + cs.fontWeight + " " + size + "px " + cs.fontFamily;
    if ("fontStretch" in g) g.fontStretch = "condensed";
    g.fillText("t", ox, by);
    var d = g.getImageData(0, 0, S, S).data, rows = [];
    for (var y = 0; y < S; y++) {
      var l = -1, r = -1;
      for (var x = 0; x < S; x++) if (d[(y * S + x) * 4 + 3] > 127) { if (l < 0) l = x; r = x; }
      if (l >= 0) rows.push({ y: y - by, l: l - ox, r: r - ox + 1 });
    }
    var bar = null;
    if (rows.length > 10) {
      var stem = rows[0].r - rows[0].l, i = 0;
      while (i < rows.length && rows[i].r - rows[i].l <= stem * 1.25) i++;
      if (i < rows.length) {
        bar = { top: rows[i].y, bottom: rows[i].y + 1, left: rows[i].l, right: rows[i].r };
        for (; i < rows.length && rows[i].r - rows[i].l > stem * 1.25; i++) {
          bar.bottom = rows[i].y + 1; bar.left = Math.min(bar.left, rows[i].l); bar.right = Math.max(bar.right, rows[i].r);
        }
        if (bar.bottom - bar.top < size * 0.05 || bar.bottom - bar.top > size * 0.4) bar = null;   // 不像横杠（兜底字体之类）
      }
    }
    return (barCache[key] = bar);
  }
  function rel(r, base) { return { left: r.left - base.left, top: r.top - base.top, right: r.right - base.left, bottom: r.bottom - base.top, width: r.width, height: r.height }; }

  // 小人和标签都不能顶出首屏上沿（窗口矮的时候麦乐鸡会顶到导航栏）：先按 CSS 的上内边距摆一次，
  // 最高的元素离上沿不足 TOP_GAP 就把上内边距加大，再摆一次
  var TOP_GAP = 16;
  function layout() {
    if (!cast.length) return;
    stage.style.paddingTop = stage.style.paddingBottom = "";
    place();
    var minTop = Infinity;
    cast.forEach(function (o) { minTop = Math.min(minTop, o.y, parseFloat(o.pill.style.top) || Infinity); });
    if (minTop < TOP_GAP) {
      // 上面加多少，下面就让出多少（下内边距至少留 24px），首屏总高度不变、不出滚动条
      var cs = getComputedStyle(stage), d = TOP_GAP - minTop;
      stage.style.paddingTop = (parseFloat(cs.paddingTop) + d) + "px";
      stage.style.paddingBottom = Math.max(24, parseFloat(cs.paddingBottom) - d) + "px";
      place();
    }
    // 手机上标签排在副标题下面，宣传片入口卡在文档流里紧跟其后：下内边距按标签实际占的高度留（320 宽时三个标签排成三行），
    // 不压到入口卡也不空出一大截。用 offsetHeight：入场动画的 scale 会让 getBoundingClientRect 的高度变小
    if (window.matchMedia("(max-width:640px)").matches) {
      var base = stage.getBoundingClientRect(), sub = document.querySelector(".stage .sub").getBoundingClientRect(), last = 0;
      cast.forEach(function (o) { last = Math.max(last, (parseFloat(o.pill.style.top) || 0) + o.pill.offsetHeight); });
      stage.style.paddingBottom = Math.max(24, last - (sub.bottom - base.top) + 14) + "px";
    }
  }
  function place() {
    var base = stage.getBoundingClientRect(), fm = fontMetrics();
    cast.forEach(function (o) {
      var h = o.c.h * fm.size, w, gr = null;
      if (o.c.pose === "burger-side") {
        // ᗰ 的图（gold-m.webp）不透明部分的底边在图高 98.5%：脚踩在这里，手指右侧那一点（anchor）对准竖笔外沿
        gr = rel(document.getElementById("ank-gold").getBoundingClientRect(), base);
        var gx = gr.left + gr.width * GOLD_GRIP.edge, gy = gr.top + gr.height * GOLD_GRIP.y, gb = gr.top + gr.height * 0.985;
        h = (gb - gy) / (1 - o.m.anchor[1] / 100);
        o.gripAt = { x: gx, y: gy };
        o.cover.style.left = gr.left + "px"; o.cover.style.top = gr.top + "px";
        o.cover.style.width = gr.width + "px"; o.cover.style.height = gr.height + "px";
      }
      w = h * o.m.aspect;
      o.a.style.width = w + "px"; o.a.style.height = h + "px";
      o.eyes.forEach(function (e) {
        e.style.setProperty("--ew", (o.m.ew / 100 * w) + "px");
        e.style.setProperty("--eh", (o.m.eh / 100 * h) + "px");
      });
      var ax = o.m.anchor[0] / 100 * w, ay = o.m.anchor[1] / 100 * h, x, y;
      if (o.c.pose === "drumstick-hang") {
        var t = document.getElementById("ank-t"), tr = rel(t.getBoundingClientRect(), base), bl = baselineOf(t) - base.top;
        var bar = crossbar(getComputedStyle(mega), fm.size), gTop = GRIP.top / 100 * h, gH = (GRIP.bottom - GRIP.top) / 100 * h;
        if (bar) {
          // 两只拳头居中在横杠上，拳头上沿高出横杠 peek 个拳头高；横杠下沿就是前后两层的分界
          x = tr.left + (bar.left + bar.right) / 2; ax = w * 0.5;
          var imgTop = bl + bar.top - GRIP.peek * gH - gTop;
          y = imgTop; ay = 0;
          var cut = (bl + bar.bottom - imgTop) / h * 100;
          o.a.style.setProperty("--cut", cut.toFixed(2) + "%");
          o.twin.style.setProperty("--cutb", (cut + 100 / h).toFixed(2) + "%");   // 手那层多留 1px，接缝处两层重叠，不出细线
        } else {
          x = tr.left + tr.width * 0.47; y = bl - fm.xh * 0.93;     // 量不出横杠：按 x 高度估，手不藏到字后面
          o.a.style.removeProperty("--cut"); o.twin.style.removeProperty("--cutb");
        }
        o.a.classList.toggle("grip", !!bar); o.twin.classList.toggle("grip", !!bar);
      } else if (o.c.pose === "nugget-sit") {
        var mm = document.getElementById("ank-m"), mr = rel(mm.getBoundingClientRect(), base), bm = baselineOf(mm) - base.top;
        x = mr.left + mr.width * 0.5; y = bm - fm.xh + 2;            // 坐在 m 的顶上
      } else {
        x = o.gripAt.x; y = o.gripAt.y;                              // 拳头扒在 ᗰ 右边缘
        o.a.classList.add("grip"); o.twin.classList.add("grip");
        var cutX = o.m.anchor[0] - gr.width * GOLD_GRIP.rim / o.w * 100;       // 图宽 %：这条竖线左边的手指画在 ᗰ 前面
        o.a.style.setProperty("--clip-front", clipOf(o.m.grip, false, cutX)); o.twin.style.setProperty("--clip-back", clipOf(o.m.grip, true, cutX));
      }
      o.x = x - ax; o.y = y - ay; o.w = w; o.h = h;
      o.a.style.left = o.x + "px"; o.a.style.top = o.y + "px";
      o.body.style.transformOrigin = o.c.pose === "drumstick-hang" ? "50% " + ((GRIP.top + GRIP.bottom) / 2) + "%" : (o.m.anchor[0]) + "% " + (o.m.anchor[1]) + "%";
      if (o.twin) {
        ["left", "top", "width", "height"].forEach(function (k) { o.twin.style[k] = o.a.style[k]; });
        o.twinBody.style.transformOrigin = o.body.style.transformOrigin;
      }
    });
    placePills(base, fm);
    placeFocus(base, fm);
  }

  // 标签：桌面上贴着各自的小人（鸡腿的放进两行字之间的空隙），手机上空隙太窄，改成副标题下面一排
  function placePills(base, fm) {
    var narrow = window.matchMedia("(max-width:640px)").matches;
    if (narrow) {
      var pad = parseFloat(getComputedStyle(stage).paddingLeft) || 0;
      var sub = document.querySelector(".stage .sub").getBoundingClientRect(), x = pad, y = sub.bottom - base.top + 18;
      // 按导航的顺序（练、拆、装）排，不按小人在标题里的位置
      cast.slice().sort(function (a, b) { return ORDER.indexOf(a.c.page) - ORDER.indexOf(b.c.page); }).forEach(function (o) {
        var pr = o.pill.getBoundingClientRect();
        if (x + pr.width > base.width - pad) { x = pad; y += pr.height + 10; }
        o.pill.style.left = x + "px"; o.pill.style.top = y + "px"; x += pr.width + 10;
      });
      return;
    }
    cast.forEach(function (o) {
      var pr = o.pill.getBoundingClientRect();
      if (o.c.side === "left") {
        var bl = baselineOf(document.getElementById("ank-t")) - base.top;
        var lineH = parseFloat(getComputedStyle(mega).lineHeight) || fm.size, gap = lineH - fm.size * 0.72;
        o.pill.style.left = (parseFloat(getComputedStyle(stage).paddingLeft) || 0) + "px";
        o.pill.style.top = (bl + Math.max(2, (gap - pr.height) / 2)) + "px";
      } else if (o.c.pose === "nugget-sit") {
        // 麦乐鸡右侧、头带高度，隔开一段留给箭头弯过去
        o.pill.style.left = (o.x + o.w + fm.size * 0.2) + "px"; o.pill.style.top = (o.y + o.h * 0.04) + "px";
      } else {
        // 汉堡头顶右侧，箭头从标签左下角弯过去指向汉堡的身体
        o.pill.style.left = (o.x + o.w + fm.size * 0.28) + "px"; o.pill.style.top = (o.y + o.h * 0.1) + "px";
      }
      if (o.arrow) pointAt(o, pr);
    });
  }

  // grip：从图左边出发、绕拳头一圈再回到图左边的折线（图宽/图高 %）。前层只显示这一块，后层显示其余部分
  function clipOf(poly, inverse, maxX) {
    var pts = poly.map(function (p) { return Math.min(p[0], maxX).toFixed(2) + "% " + p[1] + "%"; });
    if (!inverse) return "polygon(" + pts.join(",") + ")";
    return "polygon(0 0,100% 0,100% 100%,0 100%," + pts.slice().reverse().join(",") + ")";
  }

  /* ---------- 焦点构图（docs/mockups/split2/h3-focus.png）：金色 ᗰ 背后的大红圆、从「不如」绕回 ᗰ 的箭头 ---------- */
  var disc = document.getElementById("focusDisc"), loop = document.getElementById("focusLoop");
  function placeFocus(base, fm) {
    if (!disc || !loop) return;
    var gr = rel(document.getElementById("ank-gold").getBoundingClientRect(), base), em = fm.size;
    // 圆心在 ᗰ 右缘附近、略高于 ᗰ 的中线，直径约两个 ᗰ 高：ᗰ 和扒着它的汉堡一起落在圆里
    var r = gr.height * 1.05, cx = gr.left + gr.width * 0.95, cy = gr.top + gr.height * 0.45;
    disc.style.width = disc.style.height = (2 * r).toFixed(1) + "px";
    disc.style.left = (cx - r).toFixed(1) + "px"; disc.style.top = (cy - r).toFixed(1) + "px";

    // 箭头：桌面从「不如」左上方起笔、越过「不如」，手机从「不如」右边起笔；在右边绕一个大弯，回来指向红圆右下。
    // 右边留不出弯的空间（窄屏时「不如」和红圆都已经靠右）就不画
    var ru = rel(mega.querySelector(".ru").getBoundingClientRect(), base);
    var narrow = window.matchMedia("(max-width:640px)").matches, padR = parseFloat(getComputedStyle(stage).paddingRight) || 0;
    var S = narrow ? { x: ru.right + em * 0.08, y: ru.top + ru.height * 0.35 } : { x: ru.left - em * 0.16, y: ru.top - em * 0.06 };
    var E = { x: cx + r * 0.86 + em * 0.05, y: cy + r * 0.62 };
    var X = Math.min(base.width - padR * 0.4, Math.max(ru.right, cx + r) + em * 0.55);
    if (X - Math.max(S.x, E.x) < em * 0.22) { loop.style.display = "none"; return; }
    loop.style.display = "";
    var mid = (S.y + E.y) / 2, c4 = { x: E.x + em * 0.9, y: E.y + em * 0.02 };
    var n = function (v) { return v.toFixed(1); };
    var shaft = "M" + n(S.x) + " " + n(S.y) +
      " C" + n(narrow ? (S.x + X) / 2 : ru.right + em * 0.1) + " " + n(S.y - em * 0.03) + " " + n(X) + " " + n(S.y + em * 0.02) + " " + n(X) + " " + n(mid) +
      " C" + n(X) + " " + n(E.y - em * 0.02) + " " + n(c4.x) + " " + n(c4.y) + " " + n(E.x) + " " + n(E.y);
    // 箭头两翼：沿进入方向往回折 ±30°
    var ux = E.x - c4.x, uy = E.y - c4.y, ul = Math.hypot(ux, uy) || 1, L = Math.max(14, em * 0.11);
    ux /= ul; uy /= ul;
    var wing = function (deg) {
      var a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
      return n(E.x - L * (ux * c - uy * s)) + " " + n(E.y - L * (ux * s + uy * c));
    };
    loop.setAttribute("width", base.width); loop.setAttribute("height", base.height);
    loop.setAttribute("viewBox", "0 0 " + n(base.width) + " " + n(base.height));
    loop.style.strokeWidth = Math.max(2, em * 0.013).toFixed(2) + "px";
    loop.querySelector(".shaft").setAttribute("d", shaft);
    loop.querySelector(".head").setAttribute("d", "M" + wing(30) + " L" + n(E.x) + " " + n(E.y) + " L" + wing(-30));
  }

  /* ---------- 标签指向小人的手绘箭头 ---------- */
  var SVGNS = "http://www.w3.org/2000/svg";
  function mkArrow() {
    var svg = document.createElementNS(SVGNS, "svg");
    svg.setAttribute("class", "pill-arrow"); svg.setAttribute("aria-hidden", "true");
    ["shaft", "head"].forEach(function (k) {
      var p = document.createElementNS(SVGNS, "path"); p.setAttribute("class", k);
      if (k === "shaft") p.setAttribute("pathLength", "1");
      svg.appendChild(p);
    });
    return svg;
  }
  // 起点在标签朝小人那一端外侧，终点在小人身体边缘外 gap 像素；二次曲线，箭头两翼沿终点切线张开
  function pointAt(o, pr) {
    var a = o.c.arrow, ed = o.m.edges && o.m.edges[String(a.row)], gap = 10;
    if (!ed) { o.arrow.style.display = "none"; return; }
    var px = parseFloat(o.pill.style.left), py = parseFloat(o.pill.style.top);
    var E = { x: o.x + (a.edge === "L" ? ed[0] : ed[1]) / 100 * o.w + (a.edge === "L" ? -gap : gap), y: o.y + a.row / 100 * o.h };
    var S = E.x > px + pr.width ? { x: px + pr.width + 8, y: py + pr.height * 0.5 } : { x: px - 8, y: py + pr.height * 0.62 };
    var dx = E.x - S.x, dy = E.y - S.y, L = Math.hypot(dx, dy);
    if (L < 40) { o.arrow.style.display = "none"; return; }   // 标签贴着小人时不画，太短的箭头像个钩
    o.arrow.style.display = "";
    var C = { x: (S.x + E.x) / 2 - dy / L * a.bow * L, y: (S.y + E.y) / 2 + dx / L * a.bow * L };
    var tx = E.x - C.x, ty = E.y - C.y, tl = Math.hypot(tx, ty) || 1, hl = 9, ang = 0.52;
    tx /= tl; ty /= tl;
    var wing = function (k) {
      var c = Math.cos(ang * k), s = Math.sin(ang * k);
      return { x: E.x - hl * (tx * c - ty * s), y: E.y - hl * (tx * s + ty * c) };
    };
    var h1 = wing(1), h2 = wing(-1), pts = [S, C, E, h1, h2];
    var x0 = Math.min.apply(null, pts.map(function (p) { return p.x; })) - 4, y0 = Math.min.apply(null, pts.map(function (p) { return p.y; })) - 4;
    var x1 = Math.max.apply(null, pts.map(function (p) { return p.x; })) + 4, y1 = Math.max.apply(null, pts.map(function (p) { return p.y; })) + 4;
    var f = function (p) { return (p.x - x0).toFixed(1) + " " + (p.y - y0).toFixed(1); };
    o.arrow.style.left = x0 + "px"; o.arrow.style.top = y0 + "px";
    o.arrow.setAttribute("width", (x1 - x0).toFixed(1)); o.arrow.setAttribute("height", (y1 - y0).toFixed(1));
    o.arrow.firstChild.setAttribute("d", "M" + f(S) + " Q" + f(C) + " " + f(E));
    o.arrow.lastChild.setAttribute("d", "M" + f(h1) + " L" + f(E) + " L" + f(h2));
    o.arrow.style.setProperty("--nx", (tx * 3).toFixed(2) + "px"); o.arrow.style.setProperty("--ny", (ty * 3).toFixed(2) + "px");
  }

  /* ---------- 行为 ---------- */
  function hover(o, on) {
    o.hover = on;
    o.a.classList.toggle("happy", on);
    o.pill.classList.toggle("lit", on);
    if (o.arrow) o.arrow.classList.toggle("lit", on);
    if (on && !reduce && (!o.lastHop || Date.now() - o.lastHop > 1400)) { o.lastHop = Date.now(); hop(o); }
  }
  // 动作 class 同时加在手那层上，两层一起动
  function act(o, name, on) {
    o.a.classList.toggle(name, on);
    if (o.twin) o.twin.classList.toggle(name, on);
  }
  function hop(o) {
    if (reduce) return;
    if (o.c.pose === "burger-side") return tug(o, 0.7, 900);
    act(o, "hop", false); void o.a.offsetWidth; act(o, "hop", true);
    clearTimeout(o.hopT); o.hopT = setTimeout(function () { act(o, "hop", false); }, 620);
  }
  function blinkLoop(o) {
    setTimeout(function () {
      if (!o.hover) {
        o.eyes.forEach(function (e) { e.style.setProperty("--blink", "0.12"); });
        setTimeout(function () { o.eyes.forEach(function (e) { e.style.setProperty("--blink", "1"); }); }, 120);
      }
      blinkLoop(o);
    }, 2400 + Math.random() * 3800);
  }
  // 各自的小动作：鸡腿做引体向上（以拳头为原点往上收，手不离开横杠），汉堡缩回去再探头，麦乐鸡左右晃一晃
  function idleLoop(o) {
    setTimeout(function () {
      if (!o.hover && document.visibilityState === "visible") {
        if (o.c.pose === "burger-side") tug(o, 1, 1500);
        else {
          var cls = o.c.pose === "drumstick-hang" ? "pullup" : "wiggle";
          act(o, cls, true);
          setTimeout(function () { act(o, cls, false); }, 1300);
        }
      }
      idleLoop(o);
    }, 3800 + Math.random() * 4200);
  }

  // 汉堡拽 ᗰ：ᗰ 绕底边中点先往汉堡这边歪、再被推回去、晃一下停住；汉堡绕脚底跟着前后仰，
  // 每一帧再补一个平移，让拳头正好落在 ᗰ 上被抓的那一点（两边是同一条时间线，手不会脱开）
  var TUG = [[0, 0], [0.3, 3.2], [0.6, -2.2], [0.82, 0.8], [1, 0]];
  function tug(o, amp, dur) {
    if (reduce || o.tugging) return;
    var gold = document.getElementById("ank-gold");
    var gr = gold.getBoundingClientRect(), ar = o.a.getBoundingClientRect();
    var P = { x: gr.left + gr.width / 2, y: gr.top + gr.height * 0.985 };
    var A = { x: ar.left + o.m.anchor[0] / 100 * ar.width, y: ar.top + o.m.anchor[1] / 100 * ar.height };
    var F = { x: ar.left + ar.width / 2, y: ar.bottom };
    var rot = function (p, c, deg) {
      var r = deg * Math.PI / 180, cs = Math.cos(r), sn = Math.sin(r);
      return { x: c.x + (p.x - c.x) * cs - (p.y - c.y) * sn, y: c.y + (p.x - c.x) * sn + (p.y - c.y) * cs };
    };
    var ratio = (P.y - A.y) / Math.max(1, F.y - A.y), gk = [], bk = [];
    TUG.forEach(function (k) {
      var th = k[1] * amp, be = th * ratio, A1 = rot(A, P, th), A2 = rot(A, F, be);
      gk.push({ offset: k[0], transform: "rotate(" + th.toFixed(3) + "deg)" });
      bk.push({ offset: k[0], transform: "translate(" + (A1.x - A2.x).toFixed(2) + "px," + (A1.y - A2.y).toFixed(2) + "px) rotate(" + be.toFixed(3) + "deg)" });
    });
    var opt = { duration: dur, easing: "cubic-bezier(.45,0,.4,1)" };
    o.tugging = true;
    gold.style.transformOrigin = o.cover.style.transformOrigin = "50% 98.5%";
    o.a.style.transformOrigin = o.twin.style.transformOrigin = "50% 100%";
    var anims = [gold.animate(gk, opt), o.cover.animate(gk, opt), o.a.animate(bk, opt), o.twin.animate(bk, opt)];
    anims[0].finished.then(function () { o.tugging = false; }, function () { o.tugging = false; });
  }

  var idleTarget = null, idleNext = 0;
  function lookAround(now) {
    if (idleTarget && now < idleNext) return idleTarget;
    var r = stage.getBoundingClientRect();
    idleTarget = { x: r.left + r.width * Math.random(), y: r.top + r.height * (0.15 + Math.random() * 0.7) };
    idleNext = now + 1800 + Math.random() * 2600;
    return idleTarget;
  }

  function tick(now) {
    if (!document.getElementById("home").hidden) {
      var target = pointer && now - lastMove < 4000 ? pointer : lookAround(now);
      cast.forEach(function (o) {
        var r = o.body.getBoundingClientRect();
        o.eyes.forEach(function (e, i) {
          var er = e.getBoundingClientRect(), cx = er.left + er.width / 2, cy = er.top + er.height / 2;
          var dx = target.x - cx, dy = target.y - cy, d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 200);
          var ew = parseFloat(e.style.getPropertyValue("--ew")) || 6, eh = parseFloat(e.style.getPropertyValue("--eh")) || 8;
          e.style.setProperty("--dx", (dx / d * ew * 0.55 * k).toFixed(2) + "px");
          e.style.setProperty("--dy", (dy / d * eh * 0.4 * k).toFixed(2) + "px");
        });
        // 鼠标靠近：吊着的鸡腿朝鼠标荡过去，别的小人朝鼠标歪一下
        var cx = r.left + r.width / 2, cy = r.top + r.height / 2, dx = (pointer ? pointer.x : cx) - cx, dist = pointer ? Math.hypot(dx, pointer.y - cy) : 1e9;
        var lean = !reduce && pointer && now - lastMove < 4000 && dist < 320 && o.c.pose !== "burger-side" ? Math.max(-8, Math.min(8, dx / 30)) : 0;
        if (o.c.pose === "drumstick-hang" && !reduce) lean += Math.sin(now / 900) * 2.2;   // 吊着时自己轻轻荡
        o.lean += (lean - o.lean) * 0.1;
        o.body.style.setProperty("--lean", o.lean.toFixed(2) + "deg");
        if (o.twinBody) o.twinBody.style.setProperty("--lean", o.lean.toFixed(2) + "deg");
      });
    }
    requestAnimationFrame(tick);
  }

  window.addEventListener("pointermove", function (e) { pointer = { x: e.clientX, y: e.clientY }; lastMove = performance.now(); }, { passive: true });
  window.addEventListener("pointerdown", function (e) { pointer = { x: e.clientX, y: e.clientY }; lastMove = performance.now(); }, { passive: true });
  var rl; window.addEventListener("resize", function () { cancelAnimationFrame(rl); rl = requestAnimationFrame(layout); });
  document.addEventListener("mg:view", function (e) { if (!e.detail.name) requestAnimationFrame(layout); });

  Promise.all([
    fetch("assets/img/poses.json").then(function (r) { return r.json(); }),
    document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()
  ]).then(function (res) { poses = res[0]; build(); }).catch(function (err) { console.warn("[mcfit-meal-planner] 首屏小人加载失败", err); });
})();
