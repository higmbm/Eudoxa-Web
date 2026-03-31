// Fetches constants, project name, and aspect names; injects nav bar above first h1.
(async function () {
  try {
    // Fetch constants and expose globally
    const cRes = await fetch("/api/constants");
    if (cRes.ok) window.EUDOXA = await cRes.json();

    // Fetch project info and aspects in parallel
    const [projRes, aspRes] = await Promise.all([
      fetch("/api/project"),
      fetch("/api/aspects")
    ]);
    if (!projRes.ok || !aspRes.ok) return;

    const projData = await projRes.json();
    const aspData  = await aspRes.json();

    const projectName = projData.project_name || "";
    const aspects     = (aspData.rows || []).map(r => r[0]);

    const nav = document.createElement("nav");
    nav.className = "site-nav";

    function link(href, label) {
      const a = document.createElement("a");
      a.href = href;
      a.textContent = label;
      // Mark current page link
      if (a.pathname === location.pathname) a.className = "site-nav-current";
      return a;
    }

    function sep(char) {
      const s = document.createElement("span");
      s.className = "site-nav-sep";
      s.textContent = char || " | ";
      return s;
    }

    // EUDOXA prefix
    const eudoxaSpan = document.createElement("span");
    eudoxaSpan.className = "site-nav-project";
    eudoxaSpan.innerHTML = 'EUDOXA <span style="font-size:0.85em;font-weight:400;color:#aaa;">0.1</span>:';
    nav.appendChild(eudoxaSpan);
    nav.appendChild(sep(" "));

    // Project link
    nav.appendChild(link("/", "Project"));

    // Aspects group: 'Aspects#A1-A2-A3'
    nav.appendChild(sep());
    if (aspects.length > 0) {
      const aspLink = link("/aspects", "Aspects");
      nav.appendChild(aspLink);
      nav.appendChild(sep(">"));
      aspects.forEach((name, i) => {
        if (i > 0) nav.appendChild(sep("-"));
        nav.appendChild(link("/aspects/" + encodeURIComponent(name), name));
      });
    } else {
      nav.appendChild(link("/aspects", "Aspects"));
    }

    // Consequences
    nav.appendChild(sep());
    nav.appendChild(link("/consequences", "Consequences"));

    // Value differences
    nav.appendChild(sep());
    nav.appendChild(link("/vdiff-matrix", "Value differences"));

    // Insert before the first h1
    const h1 = document.querySelector("h1");
    if (h1) h1.parentNode.insertBefore(nav, h1);
    else document.body.prepend(nav);

  } catch (e) {
    // Nav is non-critical — fail silently
  }
})();