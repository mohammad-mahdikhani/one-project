const fileInput = document.getElementById("file");
const drop = document.getElementById("drop");
const fileName = document.getElementById("file-name");
const uploadForm = document.getElementById("upload-form");
const telegramForm = document.getElementById("telegram-form");
const stats = document.getElementById("stats");
const results = document.getElementById("results");
const rows = document.getElementById("rows");
const apply = document.getElementById("apply");
const applyNote = document.getElementById("apply-note");
const productsBox = document.getElementById("products");
const settingsForm = document.getElementById("settings-form");
const settingsNote = document.getElementById("settings-note");
const messages = document.getElementById("messages");
const messageList = document.getElementById("message-list");

let preview = [];
let lastFile = "telegram";

const labels = {
  update: "تطبیق شد",
  suggest: "پیشنهاد اسم",
  create: "روی سایت نیست",
  skip: "رد شد",
};

function money(value) {
  if (value === null || value === undefined || value === "") return "—";
  return Number(value).toLocaleString("fa-IR");
}

function siteSource() {
  return document.getElementById("source").value;
}

async function loadProducts() {
  const data = await (await fetch("/api/products")).json();
  productsBox.innerHTML = data
    .map(
      (item) => `<div class="item"><div><b>${item.name}</b><div class="muted mono">${item.sku || "بدون کد"}</div></div><div class="mono">${item.price_label}</div></div>`
    )
    .join("");
}

async function loadSettings() {
  const data = await (await fetch("/api/settings")).json();
  for (const [key, value] of Object.entries(data)) {
    const field = settingsForm.elements[key];
    if (field) field.value = value;
  }
  if (data.telegram_channel) document.getElementById("channel").value = data.telegram_channel;
  if (data.telegram_pages) document.getElementById("pages").value = data.telegram_pages;
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("on"));
    tab.classList.add("on");
    telegramForm.classList.toggle("hidden", tab.dataset.tab !== "telegram");
    uploadForm.classList.toggle("hidden", tab.dataset.tab !== "file");
  });
});

drop.addEventListener("dragover", (event) => {
  event.preventDefault();
  drop.classList.add("drag");
});
drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
drop.addEventListener("drop", (event) => {
  event.preventDefault();
  drop.classList.remove("drag");
  if (event.dataTransfer.files[0]) {
    fileInput.files = event.dataTransfer.files;
    fileName.textContent = event.dataTransfer.files[0].name;
  }
});
fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files[0] ? fileInput.files[0].name : "";
});

function renderPreview(data, note) {
  preview = data.results || [];
  stats.classList.remove("hidden");
  results.classList.remove("hidden");
  stats.innerHTML = `
    <div class="stat"><b>${data.counts.rows}</b>قیمت خوانده‌شده</div>
    <div class="stat"><b>${data.counts.update}</b>تطبیق قطعی</div>
    <div class="stat"><b>${data.counts.suggest}</b>پیشنهاد اسمی</div>
    <div class="stat"><b>${data.counts.create}</b>روی سایت نیست</div>`;
  rows.innerHTML = preview
    .map((item) => {
      const site = item.site_name
        ? `${item.site_name}<div class="muted mono">${item.site_sku || "بدون کد سایت"}</div>`
        : "—";
      const deltaClass = item.delta > 0 ? "delta-up" : item.delta < 0 ? "delta-down" : "";
      const delta = item.delta === null || item.delta === undefined ? "—" : money(item.delta);
      const link = item.source_url ? `<div class="muted"><a href="${item.source_url}" target="_blank">پیام کانال</a></div>` : "";
      return `<tr>
        <td><span class="badge ${item.action}">${labels[item.action]}</span><div class="muted">${item.reason}</div>${link}</td>
        <td class="mono">${item.sheet_sku || "—"}</td>
        <td>${item.sheet_name}</td>
        <td class="mono">${item.sheet_price_label}</td>
        <td>${site}</td>
        <td class="mono">${item.site_price_label}</td>
        <td class="mono ${deltaClass}">${delta}</td>
      </tr>`;
    })
    .join("");
  applyNote.textContent = note;
}

telegramForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  applyNote.textContent = "در حال خزش کانال و تطبیق اسم…";
  lastFile = document.getElementById("channel").value || "telegram";
  const response = await fetch("/api/telegram/crawl", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      channel: document.getElementById("channel").value,
      pages: document.getElementById("pages").value,
      source: siteSource(),
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    applyNote.textContent = data.error || "خزش کانال انجام نشد";
    return;
  }
  messages.classList.remove("hidden");
  messageList.innerHTML = (data.messages || [])
    .map(
      (item) => `<div class="item"><div><b><a href="${item.url}" target="_blank">${item.post}</a></b><div class="excerpt">${item.text || "بدون متن قیمت"}</div></div><div class="muted">${item.rows} کالا</div></div>`
    )
    .join("") || "<p class='muted'>پیامی با قیمت خوانا پیدا نشد.</p>";
  renderPreview(data, `از کانال ${data.channel} خوانده شد. اگر تطابق درست است اعمال کنید.`);
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files[0]) {
    fileName.textContent = "اول فایل را انتخاب کنید.";
    return;
  }
  lastFile = fileInput.files[0].name;
  const body = new FormData();
  body.append("file", fileInput.files[0]);
  body.append("source", siteSource());
  applyNote.textContent = "در حال تطابق کد و اسم…";
  const response = await fetch("/api/preview", { method: "POST", body });
  const data = await response.json();
  if (!response.ok) {
    applyNote.textContent = data.error || "فایل خوانده نشد";
    return;
  }
  messages.classList.add("hidden");
  renderPreview(data, "اگر تطابق درست است، قیمت‌ها را اعمال کنید.");
});

apply.addEventListener("click", async () => {
  if (!preview.length) return;
  apply.disabled = true;
  const response = await fetch("/api/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: lastFile,
      source: siteSource(),
      accept_suggested: document.getElementById("accept_suggested").checked,
      create_missing: document.getElementById("create_missing").checked,
      results: preview,
    }),
  });
  const data = await response.json();
  apply.disabled = false;
  if (!response.ok) {
    applyNote.textContent = data.error || "اعمال نشد";
    return;
  }
  applyNote.textContent = `${data.counts.updated} کالا به‌روز شد، ${data.counts.created} کالا ساخته شد.`;
  loadProducts();
});

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(settingsForm).entries());
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  settingsNote.textContent = "تنظیمات فروشگاه ذخیره شد.";
});

loadProducts();
loadSettings();
