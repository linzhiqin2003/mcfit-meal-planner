/* 首页宣传片入口（docs/mockups/home-promo 的 B 版）：点入口卡打开弹窗并播放。
 *   - 关闭键、Esc、点遮罩都能关；关掉就暂停，再打开从停下的地方接着放
 *   - 切到别的页面时弹窗一起关掉
 *   - 加载失败给一句看得懂的提示，细节进控制台
 *   - 不支持 <dialog> 的旧浏览器：直接在新标签页打开视频文件 */
(function () {
  "use strict";
  var entry = document.querySelector(".promo-entry"), dlg = document.getElementById("promoDlg");
  if (!entry || !dlg) return;
  var video = dlg.querySelector("video");

  function play() {
    var p = video.play();
    if (p && p.catch) p.catch(function (err) { console.warn("[mcfit-meal-planner] 宣传片播放失败", err); });
  }

  entry.addEventListener("click", function () {
    if (typeof dlg.showModal !== "function") {
      window.open(video.getAttribute("src"), "_blank", "noopener");
      return;
    }
    dlg.showModal();
    play();
  });
  dlg.querySelector(".promo-x").addEventListener("click", function () { dlg.close(); });
  // 点在遮罩上时事件目标是 dialog 本身；点视频、控制条、关闭键都不是
  dlg.addEventListener("click", function (e) { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener("close", function () { if (!video.paused) video.pause(); });
  video.addEventListener("error", function () {
    console.warn("[mcfit-meal-planner] 宣传片加载失败", video.currentSrc, video.error && video.error.code);
    dlg.classList.add("failed");
  });
  document.addEventListener("mg:view", function () { if (dlg.open) dlg.close(); });
})();
