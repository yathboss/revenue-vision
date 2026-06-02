(function () {
  const minIntroMs = 1900;
  const start = performance.now();

  function finishIntro() {
    const elapsed = performance.now() - start;
    const wait = Math.max(0, minIntroMs - elapsed);

    window.setTimeout(() => {
      document.body.classList.add("intro-ready");
      window.setTimeout(() => {
        document.body.classList.remove("intro-active");
        const intro = document.getElementById("introScreen");
        if (intro) intro.remove();
      }, 620);
    }, wait);
  }

  if (document.readyState === "complete") {
    finishIntro();
  } else {
    window.addEventListener("load", finishIntro, {once: true});
  }
})();
