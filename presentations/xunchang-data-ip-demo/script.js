const body = document.body;
const cover = document.querySelector(".cover-section");
const navLinks = Array.from(document.querySelectorAll(".chapter-nav a"));
const sections = navLinks
  .map((link) => document.querySelector(link.getAttribute("href")))
  .filter(Boolean);

function updateHeaderState() {
  if (!cover) return;
  const coverBottom = cover.getBoundingClientRect().bottom;
  body.classList.toggle("header-on-cover", coverBottom > 120);
}

function updateActiveLink() {
  let activeId = "";
  for (const section of sections) {
    const rect = section.getBoundingClientRect();
    if (rect.top <= 140) activeId = section.id;
  }
  navLinks.forEach((link) => {
    link.classList.toggle("is-active", link.getAttribute("href") === `#${activeId}`);
  });
}

function refreshPresentationState() {
  updateHeaderState();
  updateActiveLink();
}

window.addEventListener("scroll", refreshPresentationState, { passive: true });
window.addEventListener("resize", refreshPresentationState);
refreshPresentationState();
