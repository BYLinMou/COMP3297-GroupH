function updateStatus(targetId, message, tone) {
  const node = document.getElementById(targetId);
  if (!node) return;
  const stamp = new Date().toLocaleString();
  node.innerHTML = `<strong>[${stamp}]</strong> ${message}`;
  node.style.borderColor = tone === "error" ? "#d4a5a5" : "#d8ddd5";
  node.style.background = tone === "error" ? "#fff7f7" : "#fbfcfa";
}

function wireDemoButtons() {
  const buttons = document.querySelectorAll("[data-status-target]");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-status-target");
      const message = btn.getAttribute("data-message") || "Status updated.";
      const tone = btn.getAttribute("data-tone") || "normal";
      updateStatus(target, message, tone);
    });
  });
}

document.addEventListener("DOMContentLoaded", wireDemoButtons);

function wireStatusFilter() {
  const form = document.getElementById("status-filter-form");
  const select = document.getElementById("status-filter-select");
  if (!form || !select) return;

  select.addEventListener("change", () => {
    form.submit();
  });
}

document.addEventListener("DOMContentLoaded", wireStatusFilter);

function wireDefectRowLinks() {
  const rows = document.querySelectorAll(".defect-item[data-href]");
  rows.forEach((row) => {
    row.addEventListener("click", (event) => {
      const anchor = event.target.closest("a");
      if (anchor) return;
      const href = row.getAttribute("data-href");
      if (href) window.location.href = href;
    });
    row.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      const href = row.getAttribute("data-href");
      if (href) window.location.href = href;
    });
  });
}

document.addEventListener("DOMContentLoaded", wireDefectRowLinks);
