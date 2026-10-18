/* 「装」页的配料散点图 + 页脚小人谢幕（docs/mockups/bottom/n1-map.png）。
 * 散点图：data/ingredients.json（44 种配料的热量、热量误差、蛋白质、分组）画成 SVG。
 *   - 横轴热量 0–400 大卡、纵轴蛋白质 0–25 克；每个点一条横线 = 热量 ±1 个标准差
 *   - 「肉和蛋 / 面包 / 酱」三群各用红笔圈一圈：同组点的最小生成树描粗后取外轮廓（贴着点走，不会切进别的群），再画成首尾略有重叠的手绘闭合线
 *   - 三句手写批注放在图里的空白处（数据坐标见 NOTES），一支小箭头指向自己那一圈
 *   - 悬停（触屏点按）最近的点，显示名称和数值
 *   - 第一次滚进视口时：点依次出现、红圈画出来、批注写出来；之后改窗口大小只重画、不重放
 * 页脚：进入视口时三个小人依次鞠一躬。
 * 位置按容器实际宽度算（不用 viewBox 缩放），手机上字号不会被缩到看不清。 */
(function () {
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var io = "IntersectionObserver" in window;

  function once(el, fn) {
    if (!el) return;
    if (!io) return fn();
    var ob = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { ob.disconnect(); fn(); } });
    }, { threshold: 0.2 });
    ob.observe(el);
  }

  // 页脚：三个小人依次鞠躬（每次进页面后第一次看到页脚时）
  var cast = document.querySelector(".cast");
  if (cast && !reduce) {
    var armCast = function () { cast.classList.remove("bowing"); once(cast, function () { cast.classList.add("bowing"); }); };
    armCast();
    document.addEventListener("mg:view", function (e) { if (e.detail.name) armCast(); });
  }

  var box = document.getElementById("odChart"), svg = document.getElementById("odSvg"), tip = document.getElementById("odTip");
  if (!box || !svg) return;
  var NS = "http://www.w3.org/2000/svg";
  var X = [0, 400], Y = [0, 25];
  var LOOPS = ["meat", "bread", "sauce"];
  // 批注放在图里没有点的地方（数据坐标）：x 是左边缘的热量，y 是竖向中心的蛋白质
  //   肉和蛋：左上角整片空白；面包：面包群右边、肉群下沿以下（躲开安格斯面包的误差线，它到 245 大卡）；酱：右下角
  var NOTES = { meat: { x: 18, y: 21.5, to: "right" }, bread: { x: 262, y: 9, to: "left" }, sauce: { x: 262, y: 2, to: "left" } };
  var items = null, pts = [], played = false;

  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    (parent || svg).appendChild(e);
    return e;
  }
  function n(v) { return v.toFixed(1); }

  // 一群点的轮廓：不用凸包（肉和蛋这一群是斜着的长条，凸包的下沿会切过面包那一群，把好几个面包「圈进」肉里）。
  // 改成：同组的点用最小生成树连起来，每条边描成粗 2×pad 的圆头线、每个点画半径 pad 的圆，在离屏 canvas 上合成一块，
  // 再用 marching squares 沿这块的外边描一圈 —— 轮廓贴着点的真实分布走，凹进去的地方也跟着凹
  var DX = [1, 0, 1, 1, -1, 0, -1, 1, 0, 0, 0, 0, -1, 0, -1, 0], DY = [0, -1, 0, 0, 0, -1, 0, 0, 1, -1, 1, 1, 0, -1, 0, 0];
  function outline(group, pad, W, H) {
    var S = 2, gw = Math.ceil(W / S) + 4, gh = Math.ceil(H / S) + 4;
    var cv = document.createElement("canvas"); cv.width = gw; cv.height = gh;
    var g = cv.getContext("2d");
    g.setTransform(1 / S, 0, 0, 1 / S, 2, 2);
    // 模糊后再按半透明阈值取形状 ≈ 先闭后开：窄缝被填平、尖角被磨圆，轮廓像随手画的一圈而不是贴着每个点绕（不支持 filter 的浏览器就是不模糊）
    g.filter = "blur(" + Math.round(pad * 0.45) + "px)";
    g.lineWidth = pad * 2; g.lineCap = "round"; g.strokeStyle = g.fillStyle = "#000";
    var inTree = [0], rest = group.map(function (_, i) { return i; }).slice(1);   // Prim 最小生成树
    g.beginPath();
    while (rest.length) {
      var best = null;
      inTree.forEach(function (a) { rest.forEach(function (b) { var d = Math.hypot(group[a][0] - group[b][0], group[a][1] - group[b][1]); if (!best || d < best.d) best = { a: a, b: b, d: d }; }); });
      g.moveTo(group[best.a][0], group[best.a][1]); g.lineTo(group[best.b][0], group[best.b][1]);
      inTree.push(best.b); rest.splice(rest.indexOf(best.b), 1);
    }
    g.stroke();
    group.forEach(function (q) { g.beginPath(); g.arc(q[0], q[1], pad, 0, Math.PI * 2); g.fill(); });
    var px = g.getImageData(0, 0, gw, gh).data;
    var inside = function (x, y) { return x >= 0 && y >= 0 && x < gw && y < gh && px[(y * gw + x) * 4 + 3] > 127; };
    var start = null;
    for (var y = 0; y < gh && !start; y++) for (var x = 0; x < gw; x++) if (inside(x, y)) { start = [x, y]; break; }
    var cx = start[0], cy = start[1], pdx = NaN, pdy = NaN, raw = [], guard = 0;
    do {   // marching squares：沿外边走一圈，只记拐点
      var c = (inside(cx - 1, cy - 1) ? 1 : 0) + (inside(cx, cy - 1) ? 2 : 0) + (inside(cx - 1, cy) ? 4 : 0) + (inside(cx, cy) ? 8 : 0), dx, dy;
      if (c === 6) { dx = pdy === -1 ? -1 : 1; dy = 0; }
      else if (c === 9) { dx = 0; dy = pdx === 1 ? -1 : 1; }
      else { dx = DX[c]; dy = DY[c]; }
      if (dx !== pdx || dy !== pdy) { raw.push([(cx - 2) * S, (cy - 2) * S]); pdx = dx; pdy = dy; }
      cx += dx; cy += dy;
    } while ((cx !== start[0] || cy !== start[1]) && ++guard < 200000);
    return raw;
  }

  // 轮廓 → 沿边均匀取点 → 加一点固定的抖动 → 平滑闭合线，终点越过起点一小段（手画一圈收笔时的重叠）
  function loopPath(h, seed) {
    var per = 0, i;
    for (i = 0; i < h.length; i++) per += Math.hypot(h[(i + 1) % h.length][0] - h[i][0], h[(i + 1) % h.length][1] - h[i][1]);
    var N = Math.max(12, Math.round(per / 44)), step = per / N, out = [], acc = 0, j = 0, segLen;
    for (var s = 0; s < N; s++) {
      var target = s * step;
      while (true) {
        var a0 = h[j % h.length], a1 = h[(j + 1) % h.length];
        segLen = Math.hypot(a1[0] - a0[0], a1[1] - a0[1]);
        if (acc + segLen >= target || j > h.length * 2) { var t = segLen ? (target - acc) / segLen : 0; out.push([a0[0] + (a1[0] - a0[0]) * t, a0[1] + (a1[1] - a0[1]) * t]); break; }
        acc += segLen; j++;
      }
    }
    var r = seed;
    var rnd = function () { r = (r * 9301 + 49297) % 233280; return r / 233280 - 0.5; };
    out = out.map(function (q) { return [q[0] + rnd() * 2.4, q[1] + rnd() * 2.4]; });
    var seq = out.concat(out.slice(0, 3));   // 多画三段，收笔压过起笔
    var d = "M" + n(seq[0][0]) + " " + n(seq[0][1]);
    for (i = 0; i < seq.length - 1; i++) {
      var p0 = seq[Math.max(i - 1, 0)], p1 = seq[i], p2 = seq[i + 1], p3 = seq[Math.min(i + 2, seq.length - 1)];
      d += " C" + n(p1[0] + (p2[0] - p0[0]) / 6) + " " + n(p1[1] + (p2[1] - p0[1]) / 6) + " " + n(p2[0] - (p3[0] - p1[0]) / 6) + " " + n(p2[1] - (p3[1] - p1[1]) / 6) + " " + n(p2[0]) + " " + n(p2[1]);
    }
    return d;
  }

  function render() {
    if (!items) return;
    var W = box.clientWidth;
    if (!W) return;   // 页面隐藏时量不到宽度，进「装」页时再画
    var narrow = W < 640;
    var H = narrow ? Math.round(W * 0.92) : Math.round(Math.min(560, Math.max(380, W * 0.44)));
    var m = { l: narrow ? 40 : 60, r: narrow ? 10 : 20, t: 14, b: narrow ? 46 : 58 };
    var sx = function (v) { return m.l + (v - X[0]) / (X[1] - X[0]) * (W - m.l - m.r); };
    var sy = function (v) { return H - m.b - (v - Y[0]) / (Y[1] - Y[0]) * (H - m.t - m.b); };
    while (svg.lastChild && svg.lastChild.nodeName !== "desc") svg.removeChild(svg.lastChild);
    svg.setAttribute("width", W); svg.setAttribute("height", H); svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    box.classList.toggle("narrow", narrow);

    // 网格与坐标轴
    var g = el("g", { class: "od-grid" });
    for (var k = X[0]; k <= X[1]; k += 100) {
      el("line", { x1: n(sx(k)), y1: m.t, x2: n(sx(k)), y2: H - m.b }, g);
      el("text", { x: n(sx(k)), y: H - m.b + 20, "text-anchor": k === X[1] ? "end" : "middle" }, g).textContent = k;
    }
    for (k = Y[0]; k <= Y[1]; k += 5) {
      el("line", { x1: m.l, y1: n(sy(k)), x2: W - m.r, y2: n(sy(k)) }, g);
      el("text", { x: m.l - 10, y: n(sy(k) + 4), "text-anchor": "end" }, g).textContent = k;
    }
    el("line", { class: "axis", x1: m.l, y1: H - m.b, x2: W - m.r, y2: H - m.b }, g);
    el("line", { class: "axis", x1: m.l, y1: m.t, x2: m.l, y2: H - m.b }, g);
    el("text", { class: "lab", x: n((m.l + W - m.r) / 2), y: H - 8, "text-anchor": "middle" }, g).textContent = "热量（大卡）";
    var yl = el("text", { class: "lab", x: 0, y: 0, "text-anchor": "middle", transform: "translate(" + (narrow ? 11 : 16) + " " + n((m.t + H - m.b) / 2) + ") rotate(-90)" }, g);
    yl.textContent = "蛋白质（g）";

    // 误差线和点（按热量从左到右依次出现）
    var order = items.slice().sort(function (a, b) { return a.kcal - b.kcal; });
    var gb = el("g", { class: "od-bars" }), gd = el("g", { class: "od-dots" });
    pts = order.map(function (it, i) {
      var x = sx(it.kcal), y = sy(it.protein), cap = narrow ? 3 : 4;
      var x0 = sx(Math.max(X[0], it.kcal - it.sd)), x1 = sx(Math.min(X[1], it.kcal + it.sd));
      el("path", { class: "od-bar g-" + it.group, d: "M" + n(x0) + " " + n(y) + "H" + n(x1) + "M" + n(x0) + " " + n(y - cap) + "V" + n(y + cap) + "M" + n(x1) + " " + n(y - cap) + "V" + n(y + cap), style: "--i:" + i }, gb);
      var c = el("circle", { class: "od-dot g-" + it.group, cx: n(x), cy: n(y), r: narrow ? 3.4 : 4.4, style: "--i:" + i }, gd);
      return { it: it, x: x, y: y, c: c };
    });

    // 三圈红笔 + 批注 + 小箭头
    var gl = el("g", { class: "od-pen" });
    var pad = narrow ? 7 : 15, noteH = Math.max(17, Math.min(30, W * 0.024));
    LOOPS.forEach(function (grp, gi) {
      var mine = pts.filter(function (p) { return p.it.group === grp; }).map(function (p) { return [p.x, p.y]; });
      var edge = outline(mine, pad, W, H);
      el("path", { class: "od-loop", d: loopPath(edge, 17 + gi * 31), pathLength: 1, style: "--i:" + gi }, gl);
      var note = box.querySelector('.od-note[data-g="' + grp + '"]'), hand = note.querySelector("svg");
      var vb = hand.viewBox.baseVal, w = noteH * vb.width / vb.height, cfg = NOTES[grp];
      var nx = sx(cfg.x), ny = sy(cfg.y) - noteH / 2;
      if (nx + w > W - m.r) nx = W - m.r - w;
      note.style.left = n(nx) + "px"; note.style.top = n(ny) + "px"; note.style.width = n(w) + "px"; note.style.height = n(noteH) + "px";
      // 箭头：从批注朝向那一圈的一端出发，指到轮廓上离它最近的点（停在外面一点）
      var from = cfg.to === "right" ? [nx + w + 6, ny + noteH * 0.55] : [nx - 6, ny + noteH * 0.55];
      var near = edge.reduce(function (b, q) { var dd = Math.hypot(q[0] - from[0], q[1] - from[1]); return dd < b.d ? { q: q, d: dd } : b; }, { q: null, d: Infinity }).q;
      var dx = near[0] - from[0], dy = near[1] - from[1], len = Math.hypot(dx, dy) || 1;
      var to = [near[0] - dx / len * 6, near[1] - dy / len * 6];
      var bend = Math.min(40, len * 0.25), cx = (from[0] + to[0]) / 2 - dy / len * bend, cy = (from[1] + to[1]) / 2 + dx / len * bend;
      var ux = to[0] - cx, uy = to[1] - cy, ul = Math.hypot(ux, uy) || 1, L = narrow ? 7 : 10;
      ux /= ul; uy /= ul;
      var wing = function (deg) { var a = deg * Math.PI / 180; return n(to[0] - L * (ux * Math.cos(a) - uy * Math.sin(a))) + " " + n(to[1] - L * (ux * Math.sin(a) + uy * Math.cos(a))); };
      el("path", { class: "od-arrow", d: "M" + n(from[0]) + " " + n(from[1]) + " Q" + n(cx) + " " + n(cy) + " " + n(to[0]) + " " + n(to[1]), pathLength: 1, style: "--i:" + gi }, gl);
      el("path", { class: "od-arrow head", d: "M" + wing(28) + " L" + n(to[0]) + " " + n(to[1]) + " L" + wing(-28), pathLength: 1, style: "--i:" + gi }, gl);
    });
    el("circle", { class: "od-hot", r: narrow ? 8 : 9, cx: -99, cy: -99 });
  }

  // 悬停 / 点按：找 22px 以内最近的点
  function pick(e) {
    if (!pts.length) return;
    var r = svg.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    var best = null, bd = 22;
    pts.forEach(function (p) { var d = Math.hypot(p.x - x, p.y - y); if (d < bd) { bd = d; best = p; } });
    var hot = svg.querySelector(".od-hot");
    if (!best) { tip.hidden = true; hot.setAttribute("cx", -99); return; }
    hot.setAttribute("cx", n(best.x)); hot.setAttribute("cy", n(best.y));
    var it = best.it;
    tip.innerHTML = "<b></b><span></span>";
    tip.firstChild.textContent = it.name;
    tip.lastChild.textContent = Math.round(it.kcal) + " ± " + Math.round(it.sd) + " 大卡 · 蛋白质 " + it.protein + " g";
    tip.hidden = false;
    var tw = tip.offsetWidth, th = tip.offsetHeight;
    var left = Math.min(Math.max(4, best.x - tw / 2), box.clientWidth - tw - 4), top = best.y - th - 14;
    if (top < 0) top = best.y + 16;
    tip.style.left = n(left) + "px"; tip.style.top = n(top) + "px";
  }
  svg.addEventListener("pointermove", pick);
  svg.addEventListener("pointerdown", pick);
  svg.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") { tip.hidden = true; var h = svg.querySelector(".od-hot"); if (h) h.setAttribute("cx", -99); } });

  function play() {
    if (played || reduce) return;
    played = true;
    box.classList.add("seen");
    setTimeout(function () { box.classList.add("done"); }, 4200);   // 放完以后改窗口大小重画时不再重放
  }

  var rz;
  window.addEventListener("resize", function () { cancelAnimationFrame(rz); rz = requestAnimationFrame(render); });
  document.addEventListener("mg:view", function (e) { if (e.detail.name === "装") requestAnimationFrame(render); });

  fetch("data/ingredients.json").then(function (r) {
    if (!r.ok) throw new Error("ingredients.json " + r.status);
    return r.json();
  }).then(function (d) {
    items = d.items;
    render();
    once(box, play);
  }).catch(function (err) {
    console.warn("[maimen-gym] 配料数据加载失败", err);
    box.classList.add("failed");
    var msg = document.createElement("p");
    msg.className = "od-fail";
    msg.textContent = "图暂时加载不出来，可以直接下载下面的完整数据。";
    box.appendChild(msg);
  });
})();
