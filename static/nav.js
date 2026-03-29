// Fetches constants and aspect names; injects a nav bar above the page's first h1.
(async function () {
  try {
    // Fetch and expose symbol constants so all pages can reference them
    const cRes = await fetch("/api/constants");
    if (cRes.ok) window.EUDOXA = await cRes.json();

    const res = await fetch("/api/aspects");
    if (!res.ok) return;
    const data = await res.json();
    const aspects = (data.rows || []).map(r => r[0]);

    const nav = document.createElement("nav");
    nav.className = "site-nav";

    function link(href, label) {
      const a = document.createElement("a");
      a.href = href;
      a.textContent = label;
      return a;
    }

    function sep() {
      const s = document.createElement("span");
      s.className = "site-nav-sep";
      s.textContent = " | ";
      return s;
    }

    nav.appendChild(link("/", "Home"));
    aspects.forEach(name => {
      nav.appendChild(sep());
      nav.appendChild(link("/aspects/" + encodeURIComponent(name), name));
    });
    nav.appendChild(sep());
    nav.appendChild(link("/consequences", "Consequences"));
    nav.appendChild(sep());
    nav.appendChild(link("/vdiff-matrix", "Vdiff matrix"));

    // Insert before the first h1
    const h1 = document.querySelector("h1");
    if (h1) h1.parentNode.insertBefore(nav, h1);
    else document.body.prepend(nav);
  } catch (e) {
    // Nav is non-critical — fail silently
  }
})();