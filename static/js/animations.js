/**
 * PHYSIO REHAB - MASTER 3D & PERFORMANCE ANIMATION ENGINE
 * Production-ready, healthcare-focused 3D motion architecture across all devices.
 * Features:
 *   - Genuine GPU-accelerated Three.js kinetic rehabilitation visual with realistic Phong specular lighting.
 *   - Direct touch-drag and mouse parallax rotation on the 3D canvas (mobile, tablet, desktop).
 *   - Interactive multi-axis 3D perspective tilt on cards with dynamic specular glint reflection.
 *   - Coordinated GSAP 3.12+ ScrollTrigger entrance orchestrations.
 *   - 100% 'prefers-reduced-motion: reduce' compliance.
 *   - Automatic visibility fail-safes (content is NEVER trapped invisible).
 *   - Performance-tuned: automatic pause for off-screen viewport and background tabs.
 */

(function (window, document) {
  "use strict";

  // Global namespace
  window.PhysioAnimations = window.PhysioAnimations || {};

  // ── 1. ACCESSIBILITY & DEVICE CAPABILITY ──
  function isReducedMotion() {
    return !!(
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function isTouchDevice() {
    return !!(
      (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) ||
      "ontouchstart" in window ||
      navigator.maxTouchPoints > 0
    );
  }

  // ── 2. WEBGL SUPPORT DETECTION ──
  function isWebGLAvailable() {
    try {
      var canvas = document.createElement("canvas");
      return !!(
        window.WebGLRenderingContext &&
        (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
      );
    } catch (e) {
      return false;
    }
  }

  // ── 3. FAIL-SAFE REVEAL GUARD ──
  // Ensures all animated elements become visible immediately if JS, CDN, or animation stalls
  function enableFailSafeReveal() {
    setTimeout(function () {
      document
        .querySelectorAll(".gsap-fade-up, .gsap-reveal, .gsap-stagger-card")
        .forEach(function (el) {
          el.classList.add("is-revealed");
        });
    }, 850);
  }

  // ── 4. NAVBAR SCROLL OPTIMIZATION ──
  function initNavbarAnimation() {
    var header = document.getElementById("publicHeader");
    if (!header) return;

    var ticking = false;

    function onScroll() {
      if (!ticking) {
        window.requestAnimationFrame(function () {
          if (window.scrollY > 35) {
            header.classList.add("navbar-scrolled");
          } else {
            header.classList.remove("navbar-scrolled");
          }
          ticking = false;
        });
        ticking = true;
      }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // ── 5. PAGE ENTRANCE (HERO & HEADINGS) ──
  function initPageEntrance() {
    var animElements = document.querySelectorAll(
      ".gsap-fade-up, .gsap-reveal, .gsap-stagger-card"
    );

    if (isReducedMotion() || typeof window.gsap === "undefined") {
      animElements.forEach(function (el) {
        el.classList.add("is-revealed");
      });
      return;
    }

    var gsap = window.gsap;

    // A. Homepage Hero Entrance Sequence
    var heroBadge = document.querySelector(".hero .hero-badge");
    var heroTitle = document.querySelector(".hero h1");
    var heroSubtitle = document.querySelector(".hero p");
    var heroBtns = document.querySelectorAll(".hero .hero-btns > *");

    if (heroTitle) {
      var heroTl = gsap.timeline({ defaults: { ease: "power2.out" } });

      if (heroBadge) {
        heroTl.fromTo(
          heroBadge,
          { opacity: 0, y: -12, scale: 0.98 },
          { opacity: 1, y: 0, scale: 1, duration: 0.5, delay: 0.1 }
        );
      }

      heroTl.fromTo(
        heroTitle,
        { opacity: 0, y: 18 },
        { opacity: 1, y: 0, duration: 0.65 },
        "-=0.25"
      );

      if (heroSubtitle) {
        heroTl.fromTo(
          heroSubtitle,
          { opacity: 0, y: 14 },
          { opacity: 1, y: 0, duration: 0.55 },
          "-=0.3"
        );
      }

      if (heroBtns.length > 0) {
        heroTl.fromTo(
          heroBtns,
          { opacity: 0, y: 12 },
          { opacity: 1, y: 0, duration: 0.5, stagger: 0.08 },
          "-=0.25"
        );
      }
    }

    // B. Interior Page Hero (.page-hero, .treatments-hero)
    var innerHero = document.querySelector(".page-hero, .treatments-hero");
    if (innerHero) {
      var innerBadge = innerHero.querySelector(".page-hero-badge");
      var innerTitle = innerHero.querySelector("h1, .hero-title");
      var innerSubtitle = innerHero.querySelector("p, .hero-subtitle, .subtitle");
      var innerBreadcrumb = innerHero.querySelector(".breadcrumb");

      var pageTl = gsap.timeline({ defaults: { ease: "power2.out" } });
      if (innerBadge) {
        pageTl.fromTo(innerBadge, { opacity: 0, y: -10 }, { opacity: 1, y: 0, duration: 0.45, delay: 0.08 });
      }
      if (innerTitle) {
        pageTl.fromTo(innerTitle, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.6 }, "-=0.2");
      }
      if (innerSubtitle) {
        pageTl.fromTo(innerSubtitle, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.5 }, "-=0.3");
      }
      if (innerBreadcrumb) {
        pageTl.fromTo(innerBreadcrumb, { opacity: 0 }, { opacity: 1, duration: 0.4 }, "-=0.2");
      }
    }
  }

  // ── 6. SCROLL-TRIGGERED SECTION REVEALS ──
  function initScrollReveals() {
    var animElements = document.querySelectorAll(
      ".gsap-fade-up, .gsap-reveal, .gsap-stagger-card"
    );

    if (isReducedMotion() || typeof window.gsap === "undefined") {
      animElements.forEach(function (el) {
        el.classList.add("is-revealed");
      });
      return;
    }

    var gsap = window.gsap;
    var ScrollTrigger = window.ScrollTrigger;
    if (ScrollTrigger) {
      gsap.registerPlugin(ScrollTrigger);
    }

    // A. Section Headers
    document.querySelectorAll(".section-header, .section-title").forEach(function (header) {
      gsap.fromTo(
        header,
        { opacity: 0, y: 20 },
        {
          opacity: 1,
          y: 0,
          duration: 0.65,
          ease: "power2.out",
          immediateRender: false,
          scrollTrigger: {
            trigger: header,
            start: "top 88%",
            once: true,
          },
        }
      );
    });

    // B. Staggered Grid Collections (Restrained batch animation)
    var gridSelectors = [
      ".intro-content-grid > .intro-card",
      ".services-preview-grid > .service-preview-card",
      ".treatments-grid > .treatment-card",
      ".reviews-preview-grid > .review-card-dark",
      ".contact-preview-grid > .cp-card",
      ".why-grid > .why-item",
      ".values-grid > .value-card",
      ".clinic-gallery-grid > .clinic-photo-card",
      ".results-gallery-grid > .result-image-box",
      ".contact-grid .info-card",
    ];

    gridSelectors.forEach(function (selector) {
      var items = document.querySelectorAll(selector);
      if (items.length > 0) {
        var parent = items[0].parentElement;
        gsap.fromTo(
          items,
          { opacity: 0, y: 22 },
          {
            opacity: 1,
            y: 0,
            duration: 0.55,
            stagger: 0.08,
            ease: "power2.out",
            immediateRender: false,
            scrollTrigger: {
              trigger: parent || items[0],
              start: "top 86%",
              once: true,
            },
            onComplete: function () {
              items.forEach(function (item) {
                item.classList.add("is-revealed");
              });
            },
          }
        );
      }
    });

    // C. Call to Action Banners
    document.querySelectorAll(".appointment-cta-box, .booking-cta-section, .cta-section").forEach(function (cta) {
      gsap.fromTo(
        cta,
        { opacity: 0, y: 16 },
        {
          opacity: 1,
          y: 0,
          duration: 0.65,
          ease: "power2.out",
          immediateRender: false,
          scrollTrigger: {
            trigger: cta,
            start: "top 88%",
            once: true,
          },
        }
      );
    });
  }

  // ── 7. GENUINE INTERACTIVE 3D CARD TILT & SPECULAR GLINT ──
  // Applies physical 3D multi-axis perspective depth and dynamic specular reflection
  // across desktop pointers and mobile touch devices.
  function initCard3DTilt() {
    if (isReducedMotion()) return;

    var targetCards = document.querySelectorAll(
      ".intro-card, .service-preview-card, .treatment-card, .review-card-dark, .value-card, .why-item, .team-card, .cp-card, .stat-card, .summary-card"
    );

    targetCards.forEach(function (card) {
      var boundRect = null;
      var rafId = null;

      function updateTilt(clientX, clientY) {
        if (!boundRect) boundRect = card.getBoundingClientRect();
        var x = clientX - boundRect.left;
        var y = clientY - boundRect.top;
        var centerX = boundRect.width / 2;
        var centerY = boundRect.height / 2;

        // Clamped tilt angles (max +/- 4.5 degrees)
        var rotateX = ((centerY - y) / centerY) * 4.5;
        var rotateY = ((x - centerX) / centerX) * 4.5;

        // Relative percentage for specular reflection
        var pctX = Math.round((x / boundRect.width) * 100);
        var pctY = Math.round((y / boundRect.height) * 100);

        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(function () {
          card.style.setProperty("--pointer-x", pctX + "%");
          card.style.setProperty("--pointer-y", pctY + "%");
          card.style.transform =
            "perspective(1100px) rotateX(" +
            rotateX.toFixed(2) +
            "deg) rotateY(" +
            rotateY.toFixed(2) +
            "deg) translate3d(0, -6px, 12px)";
        });
      }

      function resetTilt() {
        if (rafId) cancelAnimationFrame(rafId);
        card.style.transform = "";
        boundRect = null;
      }

      // Pointer events (Desktop & fine pointers)
      card.addEventListener(
        "pointerenter",
        function (e) {
          boundRect = card.getBoundingClientRect();
          updateTilt(e.clientX, e.clientY);
        },
        { passive: true }
      );

      card.addEventListener(
        "pointermove",
        function (e) {
          updateTilt(e.clientX, e.clientY);
        },
        { passive: true }
      );

      card.addEventListener("pointerleave", resetTilt, { passive: true });

      // Touch events (Mobile & Tablet)
      card.addEventListener(
        "touchmove",
        function (e) {
          if (e.touches && e.touches.length === 1) {
            updateTilt(e.touches[0].clientX, e.touches[0].clientY);
          }
        },
        { passive: true }
      );

      card.addEventListener("touchend", resetTilt, { passive: true });
      card.addEventListener("touchcancel", resetTilt, { passive: true });
    });
  }

  // ── 8. CARD ELEVATION & BUTTON MICRO-INTERACTIONS ──
  function initInteractiveEffects() {
    var cardSelectors = [
      ".intro-card",
      ".service-preview-card",
      ".treatment-card",
      ".cp-card",
      ".why-item",
      ".value-card",
      ".team-card",
      ".result-image-box",
      ".stat-card",
      ".summary-card",
    ];

    document.querySelectorAll(cardSelectors.join(",")).forEach(function (card) {
      card.classList.add("hover-lift-3d");
    });

    document.querySelectorAll(".review-card-dark").forEach(function (card) {
      card.classList.add("hover-lift-dark");
    });

    // Buttons interactive tactile feedback
    document
      .querySelectorAll(".btn-gold, .btn-outline-light, .btn-outline-gold, .btn-submit-review")
      .forEach(function (btn) {
        btn.classList.add("btn-interactive");
      });

    initCard3DTilt();
  }

  // ── 9. GENUINE THREE.JS 3D REHABILITATION KINETIC MOTIF (WEBGL + REAL LIGHTING + TOUCH DRAG) ──
  // Interactive 3D physical biomechanical sculpture (spinal alignment & functional kinetic rings).
  // Features:
  // - Real specular Phong lighting (Directional + Point lights)
  // - Interactive touch drag on mobile/tablets & pointer damping on desktop
  // - Zero CPU vertex array loops (100% GPU matrix transforms)
  function initThreeHero(canvasId, containerId) {
    if (isReducedMotion() || !isWebGLAvailable() || typeof window.THREE === "undefined") {
      var fallbackContainer = document.getElementById(containerId);
      if (fallbackContainer) {
        var fallbackBg = fallbackContainer.querySelector(".three-hero-fallback");
        if (fallbackBg) fallbackBg.style.display = "block";
      }
      return null;
    }

    var canvas = document.getElementById(canvasId);
    var container = document.getElementById(containerId);
    if (!canvas || !container) return null;

    var THREE = window.THREE;
    var scene, camera, renderer, masterGroup;
    var ringOuter, ringInner, ringSpine, coreSphere;
    var mouseX = 0, mouseY = 0;
    var targetMouseX = 0, targetMouseY = 0;
    var animationFrameId = null;
    var isVisible = true;
    var isTabActive = true;

    // Touch drag state
    var isDragging = false;
    var previousTouchX = 0;
    var previousTouchY = 0;
    var touchVelocityX = 0;
    var touchVelocityY = 0;

    // Viewport dimensions
    var width = container.clientWidth || window.innerWidth;
    var height = container.clientHeight || (window.innerHeight * 0.85);

    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(48, width / height, 0.1, 100);
    camera.position.set(0, 0, 16);

    try {
      renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        alpha: true,
        antialias: true,
        powerPreference: "low-power",
      });
    } catch (e) {
      var fb = container.querySelector(".three-hero-fallback");
      if (fb) fb.style.display = "block";
      return null;
    }

    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));

    // ── LIGHTING SETUP (REAL DIRECTIONAL & SPECULAR HIGHLIGHTS) ──
    var ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    var dirLight = new THREE.DirectionalLight(0xfff5cc, 1.35);
    dirLight.position.set(12, 14, 10);
    scene.add(dirLight);

    var goldPointLight = new THREE.PointLight(0xF5C518, 1.6, 28);
    goldPointLight.position.set(0, 0, 4);
    scene.add(goldPointLight);

    var emeraldPointLight = new THREE.PointLight(0x10B981, 1.2, 22);
    emeraldPointLight.position.set(-5, -4, 3);
    scene.add(emeraldPointLight);

    // Master 3D Group
    masterGroup = new THREE.Group();
    masterGroup.position.set(3.2, 0.2, 0); // Desktop placement
    scene.add(masterGroup);

    // 1. Outer Kinetic Mobility Ring (Clinic Gold Phong)
    var outerGeo = new THREE.TorusGeometry(5.4, 0.065, 14, 64);
    var goldMat = new THREE.MeshPhongMaterial({
      color: 0xF5C518,
      specular: 0xffe680,
      shininess: 95,
      transparent: true,
      opacity: 0.82,
    });
    ringOuter = new THREE.Mesh(outerGeo, goldMat);
    ringOuter.rotation.x = Math.PI * 0.25;
    masterGroup.add(ringOuter);

    // 2. Inner Spinal Alignment Ring (Emerald Recovery Phong)
    var innerGeo = new THREE.TorusGeometry(4.0, 0.055, 14, 54);
    var emeraldMat = new THREE.MeshPhongMaterial({
      color: 0x10B981,
      specular: 0x6ee7b7,
      shininess: 75,
      transparent: true,
      opacity: 0.72,
    });
    ringInner = new THREE.Mesh(innerGeo, emeraldMat);
    ringInner.rotation.y = Math.PI * 0.35;
    masterGroup.add(ringInner);

    // 3. Central Kinetic Spinal Orbit Ring (Teal / Sky Phong)
    var spineGeo = new THREE.TorusGeometry(2.6, 0.048, 12, 44);
    var tealMat = new THREE.MeshPhongMaterial({
      color: 0x38BDF8,
      specular: 0xbae6fd,
      shininess: 65,
      transparent: true,
      opacity: 0.65,
    });
    ringSpine = new THREE.Mesh(spineGeo, tealMat);
    ringSpine.rotation.z = Math.PI * 0.45;
    masterGroup.add(ringSpine);

    // 4. Central Glowing Core Nucleus (Rehabilitation focus)
    var coreGeo = new THREE.SphereGeometry(0.55, 16, 16);
    var coreMat = new THREE.MeshPhongMaterial({
      color: 0xF5C518,
      emissive: 0x8a6500,
      specular: 0xffffff,
      shininess: 100,
      transparent: true,
      opacity: 0.9,
    });
    coreSphere = new THREE.Mesh(coreGeo, coreMat);
    masterGroup.add(coreSphere);

    // 5. Subtle Alignment Vertebrae Axis Nodes
    var nodeGeo = new THREE.SphereGeometry(0.2, 10, 10);
    var nodeMat = new THREE.MeshPhongMaterial({
      color: 0xF5C518,
      specular: 0xffffff,
      shininess: 85,
    });
    for (var n = 0; n < 4; n++) {
      var nodeMesh = new THREE.Mesh(nodeGeo, nodeMat);
      var angle = (n / 4) * Math.PI * 2;
      nodeMesh.position.set(Math.cos(angle) * 5.4, Math.sin(angle) * 5.4, 0);
      ringOuter.add(nodeMesh);
    }

    // ── INTERACTIVE TOUCH DRAG CONTROLS (MOBILE & TABLET) ──
    function onTouchStart(e) {
      if (e.touches && e.touches.length === 1) {
        isDragging = true;
        previousTouchX = e.touches[0].clientX;
        previousTouchY = e.touches[0].clientY;
        touchVelocityX = 0;
        touchVelocityY = 0;
      }
    }

    function onTouchMove(e) {
      if (!isDragging || !e.touches || e.touches.length !== 1) return;
      var deltaX = e.touches[0].clientX - previousTouchX;
      var deltaY = e.touches[0].clientY - previousTouchY;
      previousTouchX = e.touches[0].clientX;
      previousTouchY = e.touches[0].clientY;

      touchVelocityX = deltaX * 0.006;
      touchVelocityY = deltaY * 0.006;

      masterGroup.rotation.y += touchVelocityX;
      masterGroup.rotation.x += touchVelocityY;
    }

    function onTouchEnd() {
      isDragging = false;
    }

    container.addEventListener("touchstart", onTouchStart, { passive: true });
    container.addEventListener("touchmove", onTouchMove, { passive: true });
    container.addEventListener("touchend", onTouchEnd, { passive: true });
    container.addEventListener("touchcancel", onTouchEnd, { passive: true });

    // ── POINTER PARALLAX (DESKTOP) ──
    function onPointerMove(e) {
      if (isDragging) return;
      var clientX = e.clientX || 0;
      var clientY = e.clientY || 0;
      targetMouseX = (clientX / window.innerWidth - 0.5) * 1.3;
      targetMouseY = (clientY / window.innerHeight - 0.5) * 0.9;
    }

    window.addEventListener("pointermove", onPointerMove, { passive: true });

    // ── RESPONSIVE RESIZE HANDLER ──
    function onWindowResize() {
      if (!container || !renderer || !camera) return;
      var w = container.clientWidth || window.innerWidth;
      var h = container.clientHeight || (window.innerHeight * 0.85);

      // Center and scale visual on mobile screens; offset on desktop
      if (w < 768) {
        masterGroup.position.set(0, 0.4, 0);
        masterGroup.scale.set(0.75, 0.75, 0.75);
      } else {
        masterGroup.position.set(3.2, 0.2, 0);
        masterGroup.scale.set(1, 1, 1);
      }

      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }

    window.addEventListener("resize", onWindowResize, { passive: true });
    onWindowResize();

    // ── OBSERVERS FOR POWER & BATTERY SAVING ──
    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            isVisible = entry.isIntersecting;
            if (isVisible && isTabActive && !animationFrameId) {
              renderLoop();
            }
          });
        },
        { threshold: 0.05 }
      );
      observer.observe(container);
    }

    document.addEventListener("visibilitychange", function () {
      isTabActive = !document.hidden;
      if (isVisible && isTabActive && !animationFrameId) {
        renderLoop();
      }
    });

    // WebGL Context Loss Recovery
    canvas.addEventListener("webglcontextlost", function (e) {
      e.preventDefault();
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
      }
    }, false);

    canvas.addEventListener("webglcontextrestored", function () {
      if (isVisible && isTabActive) {
        renderLoop();
      }
    }, false);

    // ── RENDER ANIMATION LOOP ──
    function renderLoop() {
      if (!isVisible || !isTabActive) {
        animationFrameId = null;
        return;
      }

      animationFrameId = requestAnimationFrame(renderLoop);

      // Inertia decay for touch drags
      if (!isDragging) {
        touchVelocityX *= 0.94;
        touchVelocityY *= 0.94;
        masterGroup.rotation.y += touchVelocityX;
        masterGroup.rotation.x += touchVelocityY;
      }

      // Smooth pointer damping (lerp)
      mouseX += (targetMouseX - mouseX) * 0.04;
      mouseY += (targetMouseY - mouseY) * 0.04;

      // Continuous ambient gyroscopic 3D orbit
      ringOuter.rotation.z += 0.0022;
      ringOuter.rotation.x += 0.0012;

      ringInner.rotation.y += 0.0028;
      ringInner.rotation.z -= 0.0016;

      ringSpine.rotation.x += 0.0035;

      coreSphere.rotation.y += 0.005;

      // Parallax response to mouse
      if (!isDragging && Math.abs(touchVelocityX) < 0.001) {
        masterGroup.rotation.y = ringInner.rotation.y * 0.2 + mouseX * 0.35;
        masterGroup.rotation.x = -mouseY * 0.25;
      }

      renderer.render(scene, camera);
    }

    renderLoop();

    // Exported cleanup method
    return {
      destroy: function () {
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
        window.removeEventListener("pointermove", onPointerMove);
        window.removeEventListener("resize", onWindowResize);
        container.removeEventListener("touchstart", onTouchStart);
        container.removeEventListener("touchmove", onTouchMove);
        container.removeEventListener("touchend", onTouchEnd);
        container.removeEventListener("touchcancel", onTouchEnd);
        if (outerGeo) outerGeo.dispose();
        if (innerGeo) innerGeo.dispose();
        if (spineGeo) spineGeo.dispose();
        if (coreGeo) coreGeo.dispose();
        if (nodeGeo) nodeGeo.dispose();
        if (goldMat) goldMat.dispose();
        if (emeraldMat) emeraldMat.dispose();
        if (tealMat) tealMat.dispose();
        if (coreMat) coreMat.dispose();
        if (nodeMat) nodeMat.dispose();
        if (renderer) renderer.dispose();
      },
      resize: onWindowResize,
    };
  }

  // ── 10. MASTER INITIALIZER ──
  function init() {
    // Flag for CSS that GSAP is ready to orchestrate reveals
    document.documentElement.classList.add("gsap-ready");

    initNavbarAnimation();
    initInteractiveEffects();

    // Check if hero 3D canvas is present (Homepage)
    if (document.getElementById("threeHeroCanvas")) {
      window.PhysioAnimations.threeHero = initThreeHero(
        "threeHeroCanvas",
        "threeHeroContainer"
      );
    }

    // Coordinate with clinic preloader so hero and entrance animations don't run hidden
    var preloader = document.getElementById("clinic-preloader");
    var isPreloaderActive =
      preloader &&
      !preloader.classList.contains("clinic-preloader-hidden") &&
      document.documentElement.classList.contains("clinic-preloader-locked");

    var animationsStarted = false;
    function startPageAnimations() {
      if (animationsStarted) return;
      animationsStarted = true;

      requestAnimationFrame(function () {
        initPageEntrance();
        initScrollReveals();

        if (window.ScrollTrigger) {
          window.ScrollTrigger.refresh();
        }

        if (
          window.PhysioAnimations.threeHero &&
          typeof window.PhysioAnimations.threeHero.resize === "function"
        ) {
          window.PhysioAnimations.threeHero.resize();
        }
      });
    }

    if (isPreloaderActive) {
      window.addEventListener("clinic:preloader:dismissed", startPageAnimations, {
        once: true,
      });
      // Fallback timer if preloader dismissed without event
      setTimeout(startPageAnimations, 650);
    } else {
      startPageAnimations();
    }

    // Refresh ScrollTrigger calculations after full window and all images load
    window.addEventListener("load", function () {
      if (window.ScrollTrigger) {
        window.ScrollTrigger.refresh();
      }
      if (
        window.PhysioAnimations.threeHero &&
        typeof window.PhysioAnimations.threeHero.resize === "function"
      ) {
        window.PhysioAnimations.threeHero.resize();
      }
    });

    enableFailSafeReveal();
  }

  // Auto-init on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Expose API on window
  window.PhysioAnimations.init = init;
  window.PhysioAnimations.initThreeHero = initThreeHero;
  window.PhysioAnimations.initPageEntrance = initPageEntrance;
  window.PhysioAnimations.initScrollReveals = initScrollReveals;
  window.PhysioAnimations.initCard3DTilt = initCard3DTilt;

})(window, document);
