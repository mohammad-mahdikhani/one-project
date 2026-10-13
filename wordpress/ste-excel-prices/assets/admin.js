const form = document.getElementById("ste-form");
const table = document.getElementById("ste-table");
const apply = document.getElementById("ste-apply");
const stats = document.getElementById("ste-stats");
let preview = [];

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = new FormData(form);
  body.append("action", "ste_preview");
  body.append("nonce", stePrice.nonce);
  const response = await fetch(stePrice.ajax, { method: "POST", body });
  const data = await response.json();
  if (!data.success) {
    stats.textContent = data.data.message || "خطا";
    return;
  }
  preview = data.data.results;
  table.hidden = false;
  apply.hidden = false;
  table.querySelector("tbody").innerHTML = preview
    .map((item) => {
      const site = item.product ? item.product.name : "—";
      return `<tr><td class="ste-badge ste-${item.action}">${item.reason}</td><td>${item.name}</td><td>${site}</td><td>${item.price || "—"}</td></tr>`;
    })
    .join("");
  stats.textContent = `${preview.length} ردیف آماده است.`;
});

apply.addEventListener("click", async () => {
  const body = new FormData();
  body.append("action", "ste_apply");
  body.append("nonce", stePrice.nonce);
  body.append("results", JSON.stringify(preview));
  if (form.create_missing.checked) body.append("create_missing", "1");
  const response = await fetch(stePrice.ajax, { method: "POST", body });
  const data = await response.json();
  stats.textContent = data.success ? `${data.data.updated} به‌روز شد، ${data.data.created} ساخته شد.` : "اعمال نشد";
});
