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
const statusPill = document.getElementById("status-pill");
const targetNote = document.getElementById("target-note");

let preview = [];
let lastFile = "telegram";
let site = { connected: false, source: "local", url: "" };

const labels = {
  update: "تطبیق شد",
  suggest: "پیشنهاد اسم",
  create: "روی سایت نیست",
  skip: "رد شد",
};

function money(value) {
  if (value === null || value === undefined || value === "") return "—";
  return `${Number(value).toLocaleString("fa-IR")} تومان`;
}

function siteSource() {
  return document.getElementById("source").value;
}

function setStatus(data) {
  site = data;
  if (data.connected && data.url) {
    statusPill.className = "pill on";
    statusPill.textContent = `وصل به ${data.url.replace(/^https?:\/\//, "")}`;
    apply.textContent = "سینک با سایت";
  } else {
    statusPill.className = "pill off";
    statusPill.textContent = "سایت وصل نیست — کاتالوگ داخل اپ";
    apply.textContent = "اعمال روی کاتالوگ اپ";
  }
}

async function loadProducts() {
  const endpoint = site.connected ? "/api/site/products" : "/api/products";
  const response = await fetch(endpoint);
  const data = await response.json();
  if (!response.ok) {
    productsBox.innerHTML = `<p class="muted">${data.error || "کالا خوانده نشد"}</p>`;
    return;
  }
  productsBox.innerHTML = data.length
    ? data
        .map(
          (item) => `<div class="item"><div><b>${item.name}</b><div class="muted mono">${item.sku || "بدون کد"}</div></div><div class="mono">${item.price_label}</div></div>`
        )
        .join("")
    : "<p class='muted'>کالایی نیست.</p>";
}

async function loadSettings() {
  const data = await (await fetch("/api/settings")).json();
  setStatus(data);
  for (const [key, value] of Object.entries(data)) {
    const field = settingsForm.elements[key];
    if (field) field.value = value;
  }
  if (data.telegram_channel) document.getElementById("channel").value = data.telegram_channel;
  if (data.telegram_pages) document.getElementById("pages").value = data.telegram_pages;
  await loadProducts();
}

statusPill.addEventListener("click", () => {
  document.querySelector(".step").scrollIntoView({ behavior: "smooth" });
});

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
  const target = data.source === "woo" ? "سایت ووکامرس" : "کاتالوگ داخل اپ";
  targetNote.textContent = `مقصد سینک: ${target}`;
  stats.innerHTML = `
    <div class="stat"><b>${data.counts.rows}</b>قیمت خوانده‌شده</div>
    <div class="stat"><b>${data.counts.update}</b>تطبیق قطعی</div>
    <div class="stat"><b>${data.counts.suggest}</b>پیشنهاد اسمی</div>
    <div class="stat"><b>${data.counts.create}</b>روی سایت نیست</div>`;
  rows.innerHTML = preview
    .map((item) => {
      const siteName = item.site_name
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
        <td>${siteName}</td>
        <td class="mono">${item.site_price_label}</td>
        <td class="mono ${deltaClass}">${delta}</td>
      </tr>`;
    })
    .join("");
  applyNote.textContent = note;
}

telegramForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  applyNote.textContent = "در حال خواندن کانال…";
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
    applyNote.textContent = data.error || "خواندن کانال انجام نشد";
    results.classList.remove("hidden");
    return;
  }
  messages.classList.remove("hidden");
  messageList.innerHTML = (data.messages || [])
    .map(
      (item) => `<div class="item"><div><b><a href="${item.url}" target="_blank">${item.post}</a></b><div class="excerpt">${item.text || "بدون متن قیمت"}</div></div><div class="muted">${item.rows} کالا</div></div>`
    )
    .join("") || "<p class='muted'>پیامی با قیمت خوانا پیدا نشد.</p>";
  renderPreview(data, "اگر تطابق درست است، سینک را بزنید.");
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
  applyNote.textContent = "در حال خواندن فایل…";
  const response = await fetch("/api/preview", { method: "POST", body });
  const data = await response.json();
  if (!response.ok) {
    applyNote.textContent = data.error || "فایل خوانده نشد";
    results.classList.remove("hidden");
    return;
  }
  messages.classList.add("hidden");
  renderPreview(data, "اگر تطابق درست است، سینک را بزنید.");
});

apply.addEventListener("click", async () => {
  if (!preview.length) return;
  apply.disabled = true;
  applyNote.textContent = "در حال سینک…";
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
    applyNote.textContent = data.error || "سینک نشد";
    return;
  }
  const extra = (data.errors || []).length ? ` — ${(data.errors || []).length} خطا` : "";
  applyNote.textContent = `${data.counts.updated} کالا به‌روز شد، ${data.counts.created} کالا ساخته شد${extra}`;
  loadProducts();
});

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = settingsForm.querySelector("button");
  const payload = Object.fromEntries(new FormData(settingsForm).entries());
  if (!payload.wp_url || !payload.woo_key || !payload.woo_secret) {
    settingsNote.textContent = "آدرس سایت، کلید و سکرت را کامل پر کنید.";
    return;
  }
  settingsNote.textContent = "در حال تست اتصال به سایت… اگر فروشگاه سنگین باشد تا یک دقیقه صبر کنید.";
  button.disabled = true;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 70000);
  try {
    const response = await fetch("/api/site/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      settingsNote.textContent = data.error || "سایت جواب نداد. می‌توانید بدون سایت با demo کار کنید.";
      setStatus({ connected: false, url: payload.wp_url, source: "local" });
      return;
    }
    settingsNote.textContent = `وصل شد. ${data.product_count} کالا روی سایت است.`;
    setStatus({ connected: true, url: data.url, source: "woo" });
    loadProducts();
  } catch (error) {
    settingsNote.textContent = "سایت جواب نداد. آدرس را با https://shop.com بگذارید، کلید را دوباره کپی کنید و از اینترنت خود فروشگاه تست کنید.";
    setStatus({ connected: false, url: payload.wp_url, source: "local" });
  } finally {
    clearTimeout(timer);
    button.disabled = false;
  }
});

loadSettings();
