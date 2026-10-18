/* 「练」页的红笔批注（教练批注风格，docs/mockups/split2/r1-markup.png）。
 * app.js 每次改状态都会重画方案列表和训练单（innerHTML），这里监听它派发的 mg:ready / mg:state，在重画之后补上批注：
 *   - 方案 1 比方案 2 便宜时，圈住它的价格、旁边写「最便宜」（并列最低价时不写，免得说错）
 *   - 这一顿蛋白质够目标时，在蛋白质旁打勾、写「达标」（app.js 在那一格上标了 data-ok）
 *   - 「动作要领」那句话下面划一笔
 *   - 从选中的「今天练」按钮拐下来指向方案的箭头，跟着选中的按钮走；换部位时重画
 * 新插入的批注由 CSS 动画「画」出来；只是点选另一个方案时（source=ranks）方案 1 的圈不重画，免得每点一次都闪。
 * 训练单在首屏下方，所以它进入视口时才加 .seen，打勾、写字、划线和 03 的印章那时才开始画。 */
(function () {
  "use strict";
  var view = document.getElementById("v-train");
  if (!view || !view.classList.contains("coach")) return;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var body = view.querySelector(".page-body"), log = document.getElementById("log");
  var arrow = document.getElementById("trainArrow");
  var tplBest = document.getElementById("penBest"), tplOk = document.getElementById("penOk"), tplTip = document.getElementById("penTip");

  function price(li) {
    var b = li && li.querySelector("b");
    return b ? parseFloat(b.textContent.replace(/[^\d.]/g, "")) : NaN;
  }

  function ink(svg, delay) {
    if (!svg || reduce || !svg.animate) return;
    var t = delay || 0;
    Array.prototype.forEach.call(svg.querySelectorAll("path"), function (p, i) {
      var d = i ? 160 : 420;
      p.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { duration: d, delay: t, easing: "cubic-bezier(.5,0,.3,1)", fill: "backwards" });
      t += d + 40;
    });
  }

  function placeArrow(redraw) {
    var on = document.querySelector('#chips [aria-pressed="true"]');
    if (!arrow || !on || !body.offsetParent) return;
    // 按版面偏移量算（不用 getBoundingClientRect）：进页时正文还在上浮，量到的是动画中途的位置
    var x = 0, y = 0;
    for (var el = on; el && el !== body; el = el.offsetParent) { x += el.offsetLeft; y += el.offsetTop; }
    arrow.style.left = (x + on.offsetWidth / 2 - 30).toFixed(1) + "px";
    arrow.style.top = (y + on.offsetHeight + 6).toFixed(1) + "px";
    if (redraw) ink(arrow, 150);
  }

  function decorate(source) {
    var lis = document.querySelectorAll("#ranks li[data-rank]");
    if (lis.length && (lis.length === 1 || price(lis[0]) < price(lis[1])) && !lis[0].querySelector(".pen-best-note")) {
      lis[0].querySelector("b").appendChild(tplBest.content.cloneNode(true));
      lis[0].classList.toggle("still", source === "ranks");
    }
    // 无解时 app.js 只把这一行藏起来、不重画，所以要跳过隐藏的行，也不往已经有勾的格子里重复加
    var sc = document.getElementById("logScore"), pc = sc && sc.querySelector(".protein");
    if (pc && sc.style.display !== "none" && pc.getAttribute("data-ok") === "1" && !pc.querySelector(".pen-ok")) {
      pc.querySelector(".v").appendChild(tplOk.content.cloneNode(true));
    }
    // 动作要领：把「动作要领」标签后面那段文字包起来，下面划一笔
    var td = document.querySelector("#logBody tr.tip td"), k = td && td.querySelector(".k");
    var text = k && k.nextSibling;
    if (text && text.nodeType === 3 && text.textContent.trim()) {
      var mark = document.createElement("span");
      mark.className = "pen-mark";
      td.insertBefore(mark, text);
      mark.appendChild(text);
      mark.appendChild(tplTip.content.cloneNode(true));
    }
    placeArrow(source === "chips" || source === "ready");
  }

  document.addEventListener("mg:ready", function () { decorate("ready"); });
  // app.js 的数据可能在本脚本执行前就渲染完、mg:ready 已经派发过了（几个 defer 脚本之间会插进 fetch 的回调），这时直接补上
  if (document.querySelector("#ranks li[data-rank]")) decorate("ready");
  document.addEventListener("mg:state", function (e) { decorate((e.detail && e.detail.source) || ""); });
  document.addEventListener("mg:view", function (e) {
    if (e.detail.name === "练") requestAnimationFrame(function () { placeArrow(true); });
  });
  var rz;
  window.addEventListener("resize", function () {
    cancelAnimationFrame(rz);
    rz = requestAnimationFrame(function () { placeArrow(false); });
  });

  // 训练单进入视口时开始画（只在从视口外进来的那一刻触发；没有 IntersectionObserver 或减少动态效果时直接是画好的样子）
  if (!log || reduce || !("IntersectionObserver" in window)) return;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.classList.add("seen");
      io.unobserve(e.target);
    });
  }, { threshold: 0 });
  io.observe(log);
})();
