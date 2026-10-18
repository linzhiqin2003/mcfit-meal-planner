/* 「装」页的两支视频（双屏并排，docs/mockups/install/v3-pair.html）。
 *   - 大红色播放键（或点画面任何位置）：点了才加载并播放、同时打开原生控制条；暂停或播完时播放键回来（拖进度条时不闪）；加载失败时显示提示
 *   - 同一时间只放一支：一支开始播，另一支暂停
 *   - 「三组动作」的时间按钮：把教程跳到那一段并播放；教程不在视口里时先把它滚进来
 *   - 教程播到哪一组，那一组加 .on（印章填红）
 *   - 离开「装」页时两支都暂停
 * 视频是 preload="none"：跳转时如果还没加载，等 loadedmetadata 再设一次时间。 */
(function () {
  "use strict";
  var view = document.getElementById("v-install");
  var tut = document.getElementById("tutorial"), promo = document.getElementById("promo");
  if (!view || !tut || !promo) return;
  var videos = [tut, promo];
  var steps = Array.prototype.slice.call(view.querySelectorAll(".ins-step"));
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function fig(v) { return v.closest(".ins-video"); }

  function play(v) {
    v.controls = true;
    var p = v.play();
    if (p && p.catch) p.catch(function (err) { console.warn("[mcfit-meal-planner] 视频播放失败", err); });
  }

  // 还没加载时设 currentTime 只是记下「默认起播位置」，各浏览器不一定都认；元数据到了再设一次兜底（play() 会触发加载）
  function seek(v, t) {
    v.currentTime = t;
    if (v.readyState < 1) v.addEventListener("loadedmetadata", function () { v.currentTime = t; }, { once: true });
  }

  videos.forEach(function (v) {
    var btn = fig(v).querySelector(".ins-play");
    btn.addEventListener("click", function () { play(v); });
    // 开播前视频没有控制条，点画面本身原来没有任何反应（用户以为「打不开」）：没在播时点画面任何位置都开始播
    v.addEventListener("click", function () { if (!fig(v).classList.contains("playing") && v.paused) play(v); });
    // 真加载失败（网络、格式）时给一句看得懂的提示，不让画面毫无反应；细节进控制台
    v.addEventListener("error", function () {
      console.warn("[mcfit-meal-planner] 视频加载失败", v.currentSrc, v.error && v.error.code);
      fig(v).classList.add("failed");
    });
    v.addEventListener("play", function () {
      fig(v).classList.add("playing");
      videos.forEach(function (o) { if (o !== v && !o.paused) o.pause(); });
    });
    // 拖进度条时浏览器会短暂 pause，用 seeking 判断，避免播放键闪一下
    v.addEventListener("pause", function () { if (!v.seeking) fig(v).classList.remove("playing"); });
    v.addEventListener("ended", function () { fig(v).classList.remove("playing"); });
  });

  // 教程播到哪一组，那一组印章填红
  function mark() {
    var t = tut.currentTime;
    steps.forEach(function (s) {
      var on = !tut.paused && t >= parseFloat(s.getAttribute("data-from")) && t < parseFloat(s.getAttribute("data-to"));
      s.classList.toggle("on", on);
    });
  }
  ["timeupdate", "play", "pause", "seeked", "ended"].forEach(function (k) { tut.addEventListener(k, mark); });

  view.addEventListener("click", function (e) {
    var b = e.target.closest(".ins-jump");
    if (!b) return;
    var r = tut.getBoundingClientRect();
    if (r.top < 0 || r.bottom > window.innerHeight) tut.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    seek(tut, parseFloat(b.getAttribute("data-at")));
    play(tut);
  });

  document.addEventListener("mg:view", function (e) {
    if (e.detail.name !== "装") videos.forEach(function (v) { if (!v.paused) v.pause(); });
  });
})();
