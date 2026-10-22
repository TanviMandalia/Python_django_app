/**
 * PHYSIO REHAB - MASTER GSAP & THREE.JS ANIMATION ENGINE
 * Production-ready, healthcare-focused motion design.
 * Features:
 *   - GSAP 3.12+ ScrollTrigger orchestrations.
 *   - Three.js r128 ambient 3D biomechanical mobility wave on homepage hero.
 *   - Full 'prefers-reduced-motion: reduce' compliance.
 *   - Automatic visibility fail-safes (content is NEVER trapped invisible).
 *   - Performance-tuned: pauses off-screen canvas and background tabs.
 */

(function (window, document) {
  "use strict";

  // Global namespace
  window.PhysioAnimations = window.PhysioAnimations || {};

  // ── 1. ACCESSIBILITY & REDUCED MOTION CHECK ──
  function isReducedMotion() {
    return (
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  // ── 2. WEBGL SUPPORT CHECK ──
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
  // Ensures all animated elements become visible if JS or external CDN stalls
  function enableFailSafeReveal() {
    setTimeout(function () {
      document.querySelectorAll(".gsap-fade-up, .gsap-reveal, .gsap-stagger-card").forEach(function (el) {
        el.classList.add("is-revealed");
      });
    }, 1400);
  }

  // ── 4. NAVBAR SCROLL INTERACTION ──
  function initNavbarAnimation() {
    var header = document.getElementById("publicHeader");
    if (!header) return;

    var lastScrollY = window.scrollY;
    var ticking = false;

    function onScroll() {
      if (!ticking) {
        window.requestAnimationFrame(function () {
          if (window.scrollY > 40) {
            header.classList.add("navbar-scrolled");
          } else {
            header.classList.remove("navbar-scrolled");
          }
          lastScrollY = window.scrollY;
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
    if (isReducedMotion() || typeof window.gsap === "undefined") {
      document.querySelectorAll(".gsap-fade-up, .gsap-reveal").forEach(function (el) {
        el.classList.add("is-revealed");
      });
      return;
    }

    var gsap = window.gsap;

    // A. Hero Section Sequence
    var heroBadge = document.querySelector(".hero .hero-badge");
    var heroTitle = document.querySelector(".hero h1");
    var heroSubtitle = document.querySelector(".hero p");
    var heroBtns = document.querySelectorAll(".hero .hero-btns > *");

    if (heroTitle) {
      var heroTl = gsap.timeline({ defaults: { ease: "power3.out" } });

      if (heroBadge) {
        heroTl.fromTo(
          heroBadge,
          { opacity: 0, y: -16, scale: 0.95 },
          { opacity: 1, y: 0, scale: 1, duration: 0.6, delay: 0.15 }
        );
      }

      heroTl.fromTo(
        heroTitle,
        { opacity: 0, y: 24 },
        { opacity: 1, y: 0, duration: 0.8 },
        "-=0.3"
      );

      if (heroSubtitle) {
        heroTl.fromTo(
          heroSubtitle,
          { opacity: 0, y: 18 },
          { opacity: 1, y: 0, duration: 0.7 },
          "-=0.4"
        );
      }

      if (heroBtns.length > 0) {
        heroTl.fromTo(
          heroBtns,
          { opacity: 0, y: 16, scale: 0.96 },
          { opacity: 1, y: 0, scale: 1, duration: 0.6, stagger: 0.12 },
          "-=0.35"
        );
      }
    }

    // B. Page Hero on Interior Pages (.page-hero, .treatments-hero)
    var innerHero = document.querySelector(".page-hero, .treatments-hero");
    if (innerHero) {
      var innerTitle = innerHero.querySelector("h1, .hero-title");
      var innerSubtitle = innerHero.querySelector("p, .hero-subtitle, .subtitle");
      var innerBreadcrumb = innerHero.querySelector(".breadcrumb");

      var pageTl = gsap.timeline({ defaults: { ease: "power3.out" } });
      if (innerTitle) {
        pageTl.fromTo(innerTitle, { opacity: 0, y: 22 }, { opacity: 1, y: 0, duration: 0.75, delay: 0.1 });
      }
      if (innerSubtitle) {
        pageTl.fromTo(innerSubtitle, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.65 }, "-=0.4");
      }
      if (innerBreadcrumb) {
        pageTl.fromTo(innerBreadcrumb, { opacity: 0, scale: 0.96 }, { opacity: 1, scale: 1, duration: 0.5 }, "-=0.3");
      }
    }
  }

  // ── 6. SCROLL-TRIGGERED SECTION REVEALS ──
  function initScrollReveals() {
    if (isReducedMotion() || typeof window.gsap === "undefined") {
      document.querySelectorAll(".gsap-fade-up, .gsap-reveal, .gsap-stagger-card").forEach(function (el) {
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
        { opacity: 0, y: 24 },
        {
          opacity: 1,
          y: 0,
          duration: 0.8,
          ease: "power2.out",
          scrollTrigger: {
            trigger: header,
            start: "top 88%",
            once: true,
          },
        }
      );
    });

    // B. Staggered Grid Collections (Services, Treatments, Values, Reviews, Contact)
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
        // Find parent container to trigger together
        var parent = items[0].parentElement;
        gsap.fromTo(
          items,
          { opacity: 0, y: 30, scale: 0.98 },
          {
            opacity: 1,
            y: 0,
            scale: 1,
            duration: 0.7,
            stagger: 0.1,
            ease: "power2.out",
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

    // C. CTA Banners
    document.querySelectorAll(".appointment-cta-box, .booking-cta-section, .cta-section").forEach(function (cta) {
      gsap.fromTo(
        cta,
        { opacity: 0, scale: 0.97, y: 20 },
        {
          opacity: 1,
          scale: 1,
          y: 0,
          duration: 0.85,
          ease: "power3.out",
          scrollTrigger: {
            trigger: cta,
            start: "top 88%",
            once: true,
          },
        }
      );
    });

    // D. Review Summary Bar
    var reviewSummary = document.querySelector(".review-preview-summary, .review-summary-panel");
    if (reviewSummary) {
      gsap.fromTo(
        reviewSummary,
        { opacity: 0, y: 22 },
        {
          opacity: 1,
          y: 0,
          duration: 0.75,
          ease: "power2.out",
          scrollTrigger: {
            trigger: reviewSummary,
            start: "top 88%",
            once: true,
          },
        }
      );
    }
  }

  // ── 7. CARD ELEVATION & BUTTON MICRO-INTERACTIONS ──
  function initInteractiveEffects() {
    // Add hover-lift class to cards dynamically if not already applied
    var cardSelectors = [
      ".intro-card",
      ".service-preview-card",
      ".treatment-card",
      ".cp-card",
      ".why-item",
      ".value-card",
      ".result-image-box",
    ];

    document.querySelectorAll(cardSelectors.join(",")).forEach(function (card) {
      card.classList.add("hover-lift");
    });

    document.querySelectorAll(".review-card-dark").forEach(function (card) {
      card.classList.add("hover-lift-dark");
    });

    // Button interactive feedback
    document.querySelectorAll(".btn-gold, .btn-outline-light, .btn-outline-gold, .btn-submit-review").forEach(function (btn) {
      btn.classList.add("btn-interactive");
    });
  }

  // ── 8. THREE.JS BIOMECHANICAL KINETIC HERO VISUAL ──
  // Abstract movement, spinal mobility, and recovery ribbon in gold & emerald
  function initThreeHero(canvasId, containerId) {
    if (isReducedMotion() || !isWebGLAvailable() || typeof window.THREE === "undefined") {
      var container = document.getElementById(containerId);
      if (container) container.style.display = "none";
      return null;
    }

    var canvas = document.getElementById(canvasId);
    var container = document.getElementById(containerId);
    if (!canvas || !container) return null;

    var THREE = window.THREE;
    var scene, camera, renderer, particles, linesMesh;
    var mouseX = 0, mouseY = 0;
    var targetMouseX = 0, targetMouseY = 0;
    var animationFrameId = null;
    var isVisible = true;
    var isTabActive = true;

    // Size initialization
    var width = container.clientWidth || window.innerWidth;
    var height = container.clientHeight || (window.innerHeight * 0.85);

    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x0f172a, 0.04);

    camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 100);
    camera.position.z = 18;
    camera.position.y = 1;

    try {
      renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        alpha: true,
        antialias: true,
        powerPreference: "low-power",
      });
    } catch (e) {
      if (container) container.style.display = "none";
      return null;
    }

    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    // Particle Cloud forming wave of kinetic mobility
    var particleCount = 420;
    var geometry = new THREE.BufferGeometry();
    var positions = new Float32Array(particleCount * 3);
    var colors = new Float32Array(particleCount * 3);
    var scales = new Float32Array(particleCount);

    var goldColor = new THREE.Color(0xF5C518);
    var emeraldColor = new THREE.Color(0x10b981);
    var slateColor = new THREE.Color(0x38bdf8);

    var idx = 0;
    for (var i = 0; i < particleCount; i++) {
      var u = (i / particleCount) * Math.PI * 4;
      var v = (i % 20) * 0.5 - 5;
      
      var x = (i % 28) - 14 + (Math.random() - 0.5) * 0.6;
      var y = Math.sin(x * 0.3) * 2.2 + (Math.random() - 0.5) * 1.2;
      var z = Math.cos(x * 0.25) * 4 + (Math.random() - 0.5) * 3;

      positions[idx] = x;
      positions[idx + 1] = y;
      positions[idx + 2] = z;

      // Color interpolation: Gold -> Emerald -> Slate
      var mixedColor = goldColor.clone();
      if (i % 3 === 0) {
        mixedColor.lerp(emeraldColor, 0.7);
      } else if (i % 3 === 1) {
        mixedColor.lerp(slateColor, 0.6);
      }

      colors[idx] = mixedColor.r;
      colors[idx + 1] = mixedColor.g;
      colors[idx + 2] = mixedColor.b;

      scales[i] = Math.random() * 0.6 + 0.4;
      idx += 3;
    }

    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    // Circle texture for soft points
    var canvasTex = document.createElement("canvas");
    canvasTex.width = 32;
    canvasTex.height = 32;
    var ctx = canvasTex.getContext("2d");
    var grad = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
    grad.addColorStop(0, "rgba(255,255,255,1)");
    grad.addColorStop(0.4, "rgba(245,197,24,0.8)");
    grad.addColorStop(1, "rgba(245,197,24,0)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(16, 16, 16, 0, Math.PI * 2);
    ctx.fill();

    var pointTexture = new THREE.CanvasTexture(canvasTex);

    var particleMaterial = new THREE.PointsMaterial({
      size: 0.45,
      map: pointTexture,
      transparent: true,
      vertexColors: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      opacity: 0.75,
    });

    particles = new THREE.Points(geometry, particleMaterial);
    scene.add(particles);

    // Subtle Connecting Line Ribbons representing spine alignment
    var lineMaterial = new THREE.LineBasicMaterial({
      color: 0xF5C518,
      transparent: true,
      opacity: 0.14,
      blending: THREE.AdditiveBlending,
    });

    var lineGeometry = new THREE.BufferGeometry();
    var linePositions = new Float32Array(particleCount * 3);
    for (var j = 0; j < positions.length; j++) {
      linePositions[j] = positions[j];
    }
    lineGeometry.setAttribute("position", new THREE.BufferAttribute(linePositions, 3));
    linesMesh = new THREE.Line(lineGeometry, lineMaterial);
    scene.add(linesMesh);

    // Ambient lighting
    var ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    // Smooth Pointer Parallax (Desktop)
    function onPointerMove(e) {
      var clientX = e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
      var clientY = e.clientY || (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
      targetMouseX = (clientX / window.innerWidth - 0.5) * 1.8;
      targetMouseY = (clientY / window.innerHeight - 0.5) * 1.2;
    }

    window.addEventListener("pointermove", onPointerMove, { passive: true });

    // Responsive Resize Handler
    function onWindowResize() {
      if (!container || !renderer || !camera) return;
      var w = container.clientWidth || window.innerWidth;
      var h = container.clientHeight || (window.innerHeight * 0.85);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }

    window.addEventListener("resize", onWindowResize, { passive: true });

    // IntersectionObserver to pause rendering when hero is out of view
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

    // VisibilityChange to pause rendering in background tabs
    document.addEventListener("visibilitychange", function () {
      isTabActive = !document.hidden;
      if (isVisible && isTabActive && !animationFrameId) {
        renderLoop();
      }
    });

    // WebGL Context Loss Handlers
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

    // Render Animation Loop
    var clock = new THREE.Clock();

    function renderLoop() {
      if (!isVisible || !isTabActive) {
        animationFrameId = null;
        return;
      }

      animationFrameId = requestAnimationFrame(renderLoop);

      var elapsedTime = clock.getElapsedTime();

      // Smooth pointer damping (lerp)
      mouseX += (targetMouseX - mouseX) * 0.04;
      mouseY += (targetMouseY - mouseY) * 0.04;

      // Gentle undulating sine deformation for biomechanical wave motion
      var posArray = geometry.attributes.position.array;
      var linePosArray = lineGeometry.attributes.position.array;

      for (var k = 0; k < particleCount; k++) {
        var pX = posArray[k * 3];
        // Wave equation
        var waveY = Math.sin(pX * 0.35 + elapsedTime * 0.7) * 1.8 +
                    Math.cos(pX * 0.2 + elapsedTime * 0.5) * 0.9;
        
        posArray[k * 3 + 1] = waveY;
        linePosArray[k * 3 + 1] = waveY;
      }

      geometry.attributes.position.needsUpdate = true;
      lineGeometry.attributes.position.needsUpdate = true;

      // Gentle rotation & camera parallax
      particles.rotation.y = elapsedTime * 0.06 + mouseX * 0.15;
      particles.rotation.x = mouseY * 0.12;
      linesMesh.rotation.y = particles.rotation.y;
      linesMesh.rotation.x = particles.rotation.x;

      renderer.render(scene, camera);
    }

    renderLoop();

    // Cleanup method exposed for page transitions
    return {
      destroy: function () {
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
        window.removeEventListener("pointermove", onPointerMove);
        window.removeEventListener("resize", onWindowResize);
        if (geometry) geometry.dispose();
        if (lineGeometry) lineGeometry.dispose();
        if (particleMaterial) particleMaterial.dispose();
        if (lineMaterial) lineMaterial.dispose();
        if (pointTexture) pointTexture.dispose();
        if (renderer) renderer.dispose();
      },
    };
  }

  // ── 9. MASTER INITIALIZER ──
  function init() {
    // Flag for CSS that GSAP is ready to orchestrate reveals
    document.documentElement.classList.add("gsap-ready");

    initNavbarAnimation();
    initPageEntrance();
    initScrollReveals();
    initInteractiveEffects();

    // Check if hero 3D canvas is present (Homepage)
    if (document.getElementById("threeHeroCanvas")) {
      window.PhysioAnimations.threeHero = initThreeHero(
        "threeHeroCanvas",
        "threeHeroContainer"
      );
    }

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

})(window, document);
