/* Animated icons (useAnimations, MIT) — progressive enhancement.
 *
 * Any static <svg data-anim="<id>"> is upgraded to the matching Lottie
 * animation from static/vendor/useanimations/<id>.json. The static SVG stays
 * in place until the animation has rendered, so a missing file, a failed
 * fetch or disabled JavaScript simply leaves the original icon.
 *
 * data-anim-play (optional):
 *   hover          replay once when the host is hovered/focused (default)
 *   hover-reverse  play forward on enter, backward on leave (state icons)
 *   toggle         follow the host's aria-expanded (menu buttons)
 *   once           play once after the page loads (flash messages)
 *   loop           loop continuously
 * The host is the closest [data-anim-host], link, button or label.
 *
 * Reduced motion: animations stay on their first (resting) frame.
 */
(function () {
  'use strict';
  if (!window.lottie || !window.fetch) return;

  var script = document.currentScript;
  var base = (script && script.getAttribute('data-anim-base')) || '/static/vendor/useanimations/';
  var reduce = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  var cache = {};

  function load(id) {
    if (!/^[a-z0-9-]+$/.test(id)) return Promise.reject(new Error('bad id'));
    if (!cache[id]) {
      cache[id] = fetch(base + id + '.json', { credentials: 'same-origin' }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
      });
    }
    return cache[id];
  }

  function hostOf(svg) {
    return svg.closest('[data-anim-host]') || svg.closest('a, button, label, summary') || svg.parentElement;
  }

  function wire(anim, svg, mode) {
    var host = hostOf(svg);
    var still = function () { return reduce.matches; };

    if (mode === 'loop') {
      anim.loop = true;
      if (!still()) anim.play();
      return;
    }
    if (mode === 'once') {
      if (!still()) window.setTimeout(function () { anim.goToAndPlay(0, true); }, 150);
      return;
    }
    if (mode === 'toggle') {
      var sync = function () {
        var on = host.getAttribute('aria-expanded') === 'true';
        if (still()) { anim.goToAndStop(on ? anim.totalFrames - 1 : 0, true); return; }
        anim.setDirection(on ? 1 : -1);
        anim.play();
      };
      new MutationObserver(sync).observe(host, { attributes: true, attributeFilter: ['aria-expanded'] });
      return;
    }
    if (mode === 'hover-reverse') {
      var fwd = function () { if (still()) return; anim.setDirection(1); anim.play(); };
      var back = function () { if (still()) return; anim.setDirection(-1); anim.play(); };
      host.addEventListener('mouseenter', fwd);
      host.addEventListener('focusin', fwd);
      host.addEventListener('mouseleave', back);
      host.addEventListener('focusout', back);
      return;
    }
    // default: hover replay — plays once per enter, never restarts mid-play
    var replay = function () {
      if (still() || !anim.isPaused) return;
      anim.setDirection(1);
      anim.goToAndPlay(0, true);
    };
    host.addEventListener('mouseenter', replay);
    host.addEventListener('focusin', replay);
  }

  function upgrade(svg) {
    if (svg.__animDone) return;
    svg.__animDone = true;
    var id = svg.getAttribute('data-anim');
    var mode = svg.getAttribute('data-anim-play') || 'hover';
    var w = svg.getAttribute('width') || '16';
    var h = svg.getAttribute('height') || w;

    load(id).then(function (text) {
      var data = JSON.parse(text); // fresh copy: lottie mutates animationData
      var box = document.createElement('span');
      box.className = 'ua-icon' + (svg.getAttribute('class') ? ' ' + svg.getAttribute('class') : '');
      box.setAttribute('aria-hidden', 'true');
      box.style.width = w + 'px';
      box.style.height = h + 'px';
      var sw = svg.getAttribute('stroke-width');
      if (sw) box.style.setProperty('--ua-stroke', sw);
      var inline = svg.getAttribute('style');
      if (inline) box.style.cssText += ';' + inline;

      var anim = window.lottie.loadAnimation({
        container: box,
        renderer: 'svg',
        loop: false,
        autoplay: false,
        animationData: data,
        rendererSettings: { preserveAspectRatio: 'xMidYMid meet', progressiveLoad: false }
      });
      anim.addEventListener('DOMLoaded', function () {
        var el = box.querySelector('svg');
        // useAnimations draws Feather-style glyphs on a 24px grid offset by 4
        // inside a 32px artboard: crop to it so size/stroke match our icons.
        if (el && data.w === 32 && data.h === 32) el.setAttribute('viewBox', '4 4 24 24');
        anim.goToAndStop(0, true);
        if (svg.parentNode) svg.parentNode.replaceChild(box, svg);
        wire(anim, box, mode);
      });
      anim.addEventListener('data_failed', function () { anim.destroy(); });
    }).catch(function () { /* keep the static icon */ });
  }

  function scan(root) {
    var list = (root || document).querySelectorAll('svg[data-anim]');
    for (var i = 0; i < list.length; i++) upgrade(list[i]);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { scan(); });
  } else {
    scan();
  }
  window.AnimIcons = { scan: scan };
})();
