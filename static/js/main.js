// ── Navbar scroll shadow ──────────────────────────────────────────────────
const navbar = document.getElementById('navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 20);
  });
}

// ── Burger menu (mobile) ──────────────────────────────────────────────────
const burger = document.getElementById('burger');
const navLinks = document.getElementById('nav-links');
if (burger && navLinks) {
  burger.addEventListener('click', () => {
    navLinks.classList.toggle('open');
  });
  // Fermer quand on clique sur un lien
  navLinks.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => navLinks.classList.remove('open'));
  });
}

// ── Auto-dismiss flash messages ──────────────────────────────────────────
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.transition = 'opacity .4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  }, 4000);
});

// ── Plan selection (adhesion) ─────────────────────────────────────────────
document.querySelectorAll('.plan-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.plan-card').forEach(c => c.classList.remove('active'));
    card.classList.add('active');
    const input = document.getElementById('type_adhesion');
    if (input) input.value = card.dataset.value || '';
  });
});

// ── Montant don ────────────────────────────────────────────────────────────
document.querySelectorAll('.montant-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.montant-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const input = document.getElementById('montant');
    if (input) {
      input.value = btn.dataset.montant || '';
      input.dispatchEvent(new Event('input'));
    }
  });
});



/* ======================================
   HERO SLIDER
====================================== */

const slides = document.querySelectorAll(".slide");

let currentSlide = 0;

if(slides.length > 0){

  setInterval(() => {

    slides[currentSlide].classList.remove("active");

    currentSlide =
      (currentSlide + 1) % slides.length;

    slides[currentSlide].classList.add("active");

  }, 4000);

}