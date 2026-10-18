/* 首屏 ⇄ 信息页（练 / 拆 / 装）的切换。
 * 地址用 hash（#/练、#/拆、#/装），可以分享、刷新，浏览器返回键也能回首屏。
 * 转场：支持 View Transitions 的浏览器里，被点的小人（view-transition-name: hero-buddy）飞进信息页的页眉，
 * 页面内容依次浮上来；退回时反向。不支持时退化成淡入淡出。系统开了「减少动态效果」时直接切换。
 */
(function () {
  "use strict";
  var VIEWS = { "": "home", "练": "v-train", "拆": "v-split", "装": "v-install" };
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var current = null, homeScroll = 0;

  function route() {
    var h = decodeURIComponent(location.hash.replace(/^#\/?/, ""));
    return VIEWS.hasOwnProperty(h) ? h : "";
  }

  function show(name) {
    var id = VIEWS[name];
    document.querySelectorAll(".view").forEach(function (v) {
      var on = v.id === id;
      v.hidden = !on;
      v.classList.toggle("is-active", on);
    });
    document.documentElement.setAttribute("data-view", name || "home");
    // 导航和页脚小人里当前页那一项：样式（红笔下划线 / 牌子字变红）和读屏都靠 aria-current
    document.querySelectorAll(".nav a[data-go], .cast a[data-go]").forEach(function (a) {
      if (name && a.getAttribute("data-go") === name) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    document.title = name ? "「" + name + "」· 麦麦健身餐规划师" : "麦麦健身餐规划师";
    var view = document.getElementById(id);
    if (name) {
      window.scrollTo(0, 0);
      var h = view.querySelector(".page-title");
      if (h) h.focus({ preventScroll: true });
    } else {
      window.scrollTo(0, homeScroll);
    }
    document.dispatchEvent(new CustomEvent("mg:view", { detail: { name: name, el: view } }));
  }

  function go(name, opts) {
    opts = opts || {};
    if (name === current) return;
    var prev = current;
    if (!prev) homeScroll = window.scrollY;
    var back = !name;
    // 返回时：页眉头像飞回首屏上对应的小人
    var homeBuddy = document.querySelector('.hb[data-page="' + (name || prev) + '"]');
    var run = function () {
      current = name;
      if (!opts.fromPop) history.pushState(null, "", name ? "#/" + name : location.pathname + location.search);
      show(name);
    };
    if (reduce || !document.startViewTransition || prev === null) { run(); return; }
    document.documentElement.classList.toggle("vt-back", back);
    if (back) {
      // 退出前：页眉头像带名字；进入后（首屏）：小人带名字
      var avatar = document.querySelector('#' + VIEWS[prev] + " .page-avatar");
      if (avatar) avatar.style.viewTransitionName = "hero-buddy";
      var t = document.startViewTransition(function () {
        if (avatar) avatar.style.viewTransitionName = "";
        if (homeBuddy) { homeBuddy.style.viewTransitionName = "hero-buddy"; homeBuddy.classList.add("vt-whole"); }
        run();
      });
      t.finished.finally(function () {
        if (homeBuddy) { homeBuddy.style.viewTransitionName = ""; homeBuddy.classList.remove("vt-whole"); }
        document.documentElement.classList.remove("vt-back");
      });
    } else {
      // vt-whole：首屏小人有一部分画在字后面（鸡腿的手），飞走时要整只截图
      if (homeBuddy) { homeBuddy.style.viewTransitionName = "hero-buddy"; homeBuddy.classList.add("vt-whole"); }
      var t2 = document.startViewTransition(function () {
        if (homeBuddy) homeBuddy.style.viewTransitionName = "";
        var av = document.querySelector('#' + VIEWS[name] + " .page-avatar");
        if (av) av.style.viewTransitionName = "hero-buddy";
        run();
      });
      t2.finished.finally(function () {
        var av = document.querySelector('#' + VIEWS[name] + " .page-avatar");
        if (av) av.style.viewTransitionName = "";
        if (homeBuddy) homeBuddy.classList.remove("vt-whole");
      });
    }
  }

  document.addEventListener("click", function (e) {
    var a = e.target.closest("[data-go]");
    if (!a) return;
    e.preventDefault();
    go(a.getAttribute("data-go"));
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && current) go("");
  });
  window.addEventListener("popstate", function () { go(route(), { fromPop: true }); });

  window.MGRouter = { go: go, current: function () { return current; } };
  // 首次加载：按地址直接打开对应的页（不播转场）
  var first = route();
  current = first;
  show(first);
})();
