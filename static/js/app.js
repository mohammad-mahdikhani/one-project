const PRIMARY = [
  ["pos", "فروش"],
  ["dashboard", "پیشخوان"],
  ["products", "کالا", "admin"],
  ["register", "صندوق"],
];
const MORE = [
  ["inventory", "انبار", "admin"],
  ["accounts", "حسابداری", "admin"],
  ["customers", "مشتریان"],
  ["licenses", "لایسنس", "admin"],
  ["sms", "پیامک", "admin"],
  ["settings", "تنظیمات", "admin"],
];
const NAV = [...PRIMARY, ...MORE];
const TITLES = Object.fromEntries(NAV.map(([id, title]) => [id, title]));
const PAY = { cash: "نقد", card: "کارت", gateway: "درگاه وب‌بیکری", credit: "نسیه" };
const LICENSE_STATUS = { paid: "پرداخت‌شده", pending: "در انتظار پرداخت", canceled: "لغو" };
const TYPES = { asset: "دارایی", liability: "بدهی", equity: "سرمایه", income: "درآمد", expense: "هزینه", person: "شخص" };
const KINDS = { sale: "فروش", purchase: "خرید", adjust: "تعدیل", price: "تغییر قیمت" };
const PAGE_SIZE = 60;

const state = {
  user: null,
  mustChange: false,
  bootstrap: null,
  authView: "login",
  recovery: null,
  pendingEmail: "",
  verifyNote: "",
  authError: "",
  authDraft: null,
  update: null,
  page: "dashboard",
  busy: false,
  modal: null,
  chart: "week",
  focusBarcode: false,
  products: [],
  productQuery: "",
  posLimit: PAGE_SIZE,
  productLimit: PAGE_SIZE,
  inventoryLimit: PAGE_SIZE,
  inventoryQuery: "",
  cart: [],
  discountType: "amount",
  discountValue: "",
  buyerFirst: "",
  buyerLast: "",
  buyerPhone: "",
  posQuery: "",
  pending: [],
  dashboard: null,
  sales: [],
  registerInfo: null,
  inventory: null,
  accounts: null,
  journal: [],
  accountId: "",
  customers: [],
  licenses: null,
  access: null,
  plan: "12m",
  more: false,
  sms: [],
  settings: null,
  users: [],
  importResult: null,
  importFile: null,
  support: false,
  supportTab: "chat",
  supportLog: [],
  lastError: "",
};

const $app = () => document.getElementById("app");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}
const numberFormat = new Intl.NumberFormat("fa-IR");
function money(value) {
  return `${numberFormat.format(Math.round(Number(value) || 0))} تومان`;
}
function num(value) {
  return numberFormat.format(Number(value) || 0);
}
function asInt(value) {
  const clean = String(value ?? "")
    .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))
    .replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d))
    .replace(/[^\d-]/g, "");
  const parsed = Number(clean);
  return Number.isFinite(parsed) ? Math.round(parsed) : 0;
}
function safeImg(src) {
  if (!src) return "";
  if (src.startsWith("/uploads/") || src.startsWith("https://") || src.startsWith("http://")) return src;
  return "";
}
function thumb(src, alt, small) {
  const safe = safeImg(src);
  if (!safe) return `<span class="ph ${small ? "sm" : ""}"></span>`;
  return `<img class="${small ? "thumb sm" : ""}" src="${esc(safe)}" alt="${esc(alt || "")}" loading="lazy" decoding="async">`;
}
function remedyFor(message) {
  const text = String(message || "");
  if (text.includes("قطع شد")) return "دفترچی را ببندید و دوباره باز کنید. اگر فروش ثبت شده، همان فاکتور را دوباره نزنید.";
  if (text.includes("ستون نام") || text.includes("نام کالا")) return "ردیف اول اکسل باید نام کالا و قیمت فروش باشد. شناسه اگر نیست، همان نام کالا کافی است.";
  if (text.includes("Consumer") || text.includes("ووکامرس") || text.includes("کلید مصرف")) return "در تنظیمات، کلید ووکامرس را با ck_ بچسبانید و دسترسی را خواندن و نوشتن بگذارید.";
  if (text.includes("صندوق")) return "از زبانه صندوق، صندوق را باز کنید و فروش را دوباره بزنید.";
  if (text.includes("وارد نشده")) return "یک بار خارج شوید و دوباره وارد شوید.";
  if (text.includes("توکن") || text.includes("تلگرام") || text.includes("شناسه چت")) return "در تنظیمات، توکن ربات تلگرام و شناسه چت را ذخیره کنید.";
  return "اگر دوباره پیش آمد، گزارش خطا را بزنید تا متن برای پشتیبانی تلگرام برود.";
}
function toast(message, options) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  const problem = Boolean(options && options.error);
  if (problem) state.lastError = String(message || "");
  const report = problem && state.user ? `<button type="button" class="btn" data-act="report-error">گزارش این خطا</button>` : "";
  el.innerHTML = problem
    ? `<p>${esc(message)}</p><p class="toast-remedy">${esc(remedyFor(message))}</p>${report}`
    : esc(message);
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), problem ? 12000 : 8000);
}
function hideToast() {
  const el = document.getElementById("toast");
  if (el) el.classList.remove("show");
  clearTimeout(toast.timer);
}
async function api(path, { method = "GET", body, form } = {}) {
  const opts = { method, credentials: "same-origin" };
  if (form) opts.body = form;
  else if (body !== undefined) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    throw new Error("ارتباط با دفترچی قطع شد. اگر برنامه تازه نصب شده، آن را ببندید و دوباره باز کنید.");
  }
  const raw = await res.text();
  let data = {};
  if (raw) {
    try { data = JSON.parse(raw); }
    catch { data = { error: raw.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 180) }; }
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) data = {};
  if (!res.ok) {
    const message = data.error || (res.status === 401 ? "وارد نشده‌اید" : `درخواست انجام نشد (${res.status})`);
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    if (res.status === 401 && !String(path).includes("/api/auth/login")) {
      state.user = null;
      render();
    }
    throw err;
  }
  return data;
}
async function loadUpdate() {
  try { state.update = await api("/api/update"); }
  catch { state.update = null; }
}
function isAdmin() { return state.user?.role === "admin"; }
function allowed(page) {
  const item = NAV.find((row) => row[0] === page);
  if (!item) return false;
  return item[2] !== "admin" || isAdmin();
}
async function guard(fn) {
  if (state.busy) return;
  state.busy = true;
  try { await fn(); }
  catch (err) {
    const message = err.message || "درخواست انجام نشد";
    if (!state.user) {
      state.authError = message;
      render();
    }
    toast(message, { error: true });
  }
  finally { state.busy = false; }
}

const loaders = {
  async dashboard() {
    const updatePromise = loadUpdate();
    const [summary, sales, registerInfo] = await Promise.all([
      api("/api/reports/summary"), api("/api/sales?limit=8"), api("/api/register"),
    ]);
    state.dashboard = summary;
    state.sales = sales.sales;
    state.registerInfo = registerInfo;
    updatePromise.then(() => { if (state.page === "dashboard") paintChrome(); });
  },
  async pos() {
    const [products, pending, registerInfo] = await Promise.all([
      api("/api/products"), api("/api/sales?status=pending&limit=20"), api("/api/register"),
    ]);
    state.products = stampProducts(products.products);
    state.posLimit = PAGE_SIZE;
    state.pending = pending.sales;
    state.registerInfo = registerInfo;
    syncCartStock();
  },
  async products() {
    state.products = stampProducts((await api("/api/products")).products);
    state.productLimit = PAGE_SIZE;
  },
  async inventory() {
    state.inventory = await api("/api/inventory");
    state.inventoryLimit = PAGE_SIZE;
  },
  async accounts() {
    const [accounts, journal] = await Promise.all([
      api("/api/accounts"),
      api("/api/journal" + (state.accountId ? `?account_id=${state.accountId}` : "")),
    ]);
    state.accounts = accounts;
    state.journal = journal.entries;
  },
  async register() {
    state.registerInfo = await api("/api/register");
  },
  async licenses() {
    state.licenses = await api("/api/licenses");
    if (state.licenses?.access) state.access = state.licenses.access;
  },
  async customers() {
    state.customers = (await api("/api/customers")).customers;
  },
  async sms() {
    state.sms = (await api("/api/sms")).messages;
  },
  async settings() {
    const updatePromise = loadUpdate();
    const [settings, users] = await Promise.all([api("/api/settings"), api("/api/users")]);
    state.settings = settings.settings;
    state.users = users.users;
    updatePromise.then(() => { if (state.page === "settings") paintChrome(); });
  },
};

async function navigate(page) {
  if (!allowed(page)) page = "dashboard";
  state.page = page;
  state.more = false;
  state.modal = null;
  if (location.hash !== `#${page}`) location.hash = page;
  await loaders[page]();
  render();
}

function cartSubtotal() {
  return state.cart.reduce((sum, line) => sum + line.price * line.qty, 0);
}
function cartDiscount() {
  const subtotal = cartSubtotal();
  if (state.discountType === "percent") {
    const pct = Math.max(0, Math.min(100, Math.round(asInt(state.discountValue))));
    return Math.floor((subtotal * pct + 50) / 100);
  }
  return Math.min(subtotal, Math.max(0, asInt(state.discountValue)));
}
function syncPos() {
  const read = (id, key) => {
    const el = document.getElementById(id);
    if (el) state[key] = el.value;
  };
  read("discount", "discountValue");
  read("discount-type", "discountType");
  read("buyer-first", "buyerFirst");
  read("buyer-last", "buyerLast");
  read("buyer-phone", "buyerPhone");
  read("pos-query", "posQuery");
}
function variationOf(product, variationId) {
  return (product?.variations || []).find((item) => item.id === Number(variationId)) || null;
}
function sellableStock(product, variation) {
  if (variation) {
    return { tracked: variation.tracked !== false, stock: variation.tracked === false ? 0 : Number(variation.stock || 0), inStock: !!variation.in_stock };
  }
  return { tracked: true, stock: Number(product?.stock || 0), inStock: Number(product?.stock || 0) > 0 };
}
function syncCartStock() {
  state.cart = state.cart.map((line) => {
    const product = state.products.find((item) => item.id === line.id);
    if (!product) return null;
    const variation = line.variationId ? variationOf(product, line.variationId) : null;
    if (line.variationId && !variation) return null;
    const limits = sellableStock(product, variation);
    if (!limits.inStock) return null;
    const name = variation ? `${product.name} — ${variation.label}` : product.name;
    const price = variation ? variation.price : product.price;
    const stock = limits.tracked ? limits.stock : line.qty;
    return { ...line, name, price, stock, tracked: limits.tracked, qty: limits.tracked ? Math.min(line.qty, stock) : line.qty };
  }).filter(Boolean);
}
function addProduct(product, variation) {
  if (!product) return;
  if (product.type === "variable" && !variation) {
    if (!product.variations?.length) return toast("این کالای متغیر هنوز نوعی ندارد. دوباره از ووکامرس دریافت کنید.");
    state.modal = { type: "variations", product };
    render();
    return;
  }
  const limits = sellableStock(product, variation);
  if (limits.tracked && limits.stock <= 0) return toast("این کالا موجودی ندارد");
  if (!limits.tracked && !limits.inStock) return toast("این متغیر ناموجود است");
  const variationId = variation ? variation.id : 0;
  const line = state.cart.find((item) => item.id === product.id && (item.variationId || 0) === variationId);
  const cap = limits.tracked ? limits.stock : 1000000;
  if ((line?.qty || 0) + 1 > cap) return toast("موجودی کافی نیست");
  if (line) line.qty += 1;
  else state.cart.push({
    id: product.id,
    variationId,
    name: variation ? `${product.name} — ${variation.label}` : product.name,
    price: variation ? variation.price : product.price,
    qty: 1,
    stock: limits.tracked ? limits.stock : 1000000,
    tracked: limits.tracked,
    image: (variation && variation.image) || product.image,
  });
  state.modal = null;
  state.focusBarcode = true;
  render();
}
function matchCode(product, code) {
  if (product.barcode === code || product.sku === code) return { product, variation: null, parent: true };
  const variation = (product.variations || []).find((item) => item.barcode === code || item.sku === code);
  return variation ? { product, variation, parent: false } : null;
}
async function addByBarcode(code) {
  const trimmed = code.trim();
  if (trimmed.length < 3) return;
  let hit = state.products.map((product) => matchCode(product, trimmed)).find(Boolean);
  if (!hit) {
    const data = await api(`/api/products?q=${encodeURIComponent(trimmed)}`);
    hit = data.products.map((product) => matchCode(product, trimmed)).find(Boolean);
  }
  if (!hit) return toast("کالایی با این بارکد نیست");
  if (hit.parent && hit.product.type === "variable") return addProduct(hit.product);
  addProduct(hit.product, hit.variation);
  const input = document.getElementById("barcode");
  if (input) input.value = "";
}

function updateBanner() {
  if (!state.update?.update) return "";
  return `<div class="banner">نسخه ${esc(state.update.version)} آماده است. دانلود کنید و روی همین دفترچی نصب کنید. فروش و حساب‌ها می‌مانند.
    <a class="btn" href="${esc(state.update.url)}" target="_blank" rel="noopener">دانلود نصب‌کننده</a>
    ${state.update.notes ? `<div class="hint">${esc(state.update.notes)}</div>` : ""}
  </div>`;
}
function supportHtml() {
  const update = state.update;
  const fresh = update?.update;
  const log = state.supportLog || [];
  const bubbles = log.length
    ? log.map((item) => `<article class="bubble ${item.kind === "bug" ? "bug" : ""}"><strong>${item.kind === "bug" ? "گزارش خطا" : "چت"}</strong><p>${esc(item.body)}</p>${item.detail ? `<p class="toast-remedy">${esc(item.detail)}</p>` : ""}</article>`).join("")
    : `<p class="empty">هنوز پیامی نیست.</p>`;
  const panel = state.supportTab === "bug"
    ? `<form data-act="send-support"><input type="hidden" name="kind" value="bug"><div class="field"><label>چه اتفاقی افتاد؟</label><textarea name="body" required rows="4">${esc(state.lastError || "")}</textarea></div><button class="btn primary" type="submit">ارسال گزارش</button></form>`
    : state.supportTab === "update"
      ? `<div class="stats update-stats"><div class="stat"><small>نسخه شما</small><strong class="num">${esc(update?.current || "")}</strong></div><div class="stat"><small>نسخه انتشار</small><strong class="num">${esc(fresh ? update.version : (update?.current || ""))}</strong></div></div><p>${fresh ? `نسخه ${esc(update.version)} آماده است. فایل را دانلود کنید و روی همین دفترچی اجرا کنید. فروش و حساب‌ها می‌مانند.` : "همین نسخه برای انتشار است. فروش و حساب‌ها با به‌روزرسانی پاک نمی‌شوند."}</p>${update?.notes ? `<p class="hint">${esc(update.notes)}</p>` : ""}${fresh ? `<a class="btn primary" href="${esc(update.url)}" target="_blank" rel="noopener">دانلود نسخه تازه</a>` : ""}<button type="button" class="btn" data-act="check-update">بررسی دوباره</button>`
      : `<div class="chat-log">${bubbles}</div><form data-act="send-support"><input type="hidden" name="kind" value="chat"><div class="field"><label>پیام</label><textarea name="body" required rows="3" placeholder="برای پشتیبانی بنویسید"></textarea></div><button class="btn primary" type="submit">ارسال به تلگرام</button></form>`;
  const sheet = state.support ? `<section class="support-sheet" data-act="stop"><div class="row-actions"><strong>پشتیبانی دفترچی</strong><button type="button" class="btn" data-act="toggle-support">بستن</button></div><div class="seg">${[["chat", "چت"], ["bug", "گزارش خطا"], ["update", "به‌روزرسانی"]].map(([id, label]) => `<button type="button" class="${state.supportTab === id ? "on" : ""}" data-act="support-tab" data-tab="${id}">${label}</button>`).join("")}</div>${panel}</section>` : "";
  return `${sheet}<button type="button" class="dock" data-act="toggle-support">${state.support ? "بستن پشتیبانی" : "پشتیبانی"}</button>`;
}
function authProblem() {
  if (!state.authError) return "";
  return `<p class="form-error">${esc(state.authError)}</p>`;
}
function authHtml() {
  const draft = state.authDraft || {};
  if (state.authView === "verify") {
    return `<div class="auth"><form class="card auth-card" data-act="verify">
      <div class="brand"><div class="mark">${logo()}</div><div><strong>تأیید جیمیل</strong><span>دفترچی</span></div></div>
      <p class="hint">${esc(state.verifyNote || "کد شش‌رقمی به جیمیل فرستاده شد. صندوق ورودی و هرزنامه را ببینید.")}</p>
      ${authProblem()}
      <div class="field"><label>جیمیل</label><input class="ltr" name="ident" value="${esc(state.pendingEmail || draft.ident || "")}" required></div>
      <div class="field"><label>کد ۶ رقمی</label><input class="ltr" name="code" inputmode="numeric" autocomplete="one-time-code" required></div>
      <button class="btn primary block" type="submit">تأیید حساب</button>
      <button class="btn block" type="button" data-act="resend-verify">ارسال دوباره کد</button>
      <button class="btn block" type="button" data-act="show-login">بازگشت به ورود</button>
    </form></div>`;
  }
  if (state.authView === "register") {
    return `<div class="auth"><form class="card auth-card" data-act="register">
      <div class="brand"><div class="mark">${logo()}</div><div><strong>ساخت حساب</strong><span>با جیمیل</span></div></div>
      <p class="hint">کد تأیید از هاست وب‌بیکری به همین جیمیل می‌رود. بدون اتصال به هاست حساب ساخته نمی‌شود.</p>
      ${authProblem()}
      <div class="field"><label>نام</label><input name="name" required value="${esc(draft.name || "")}"></div>
      <div class="field"><label>موبایل</label><input class="ltr" name="phone" required placeholder="09..." value="${esc(draft.phone || "")}"></div>
      <div class="field"><label>جیمیل</label><input class="ltr" name="email" type="email" required placeholder="name@gmail.com" value="${esc(draft.email || "")}"></div>
      <div class="field"><label>رمز</label><input type="password" name="password" required value="${esc(draft.password || "")}"></div>
      <button class="btn primary block" type="submit">ساخت حساب</button>
      <button class="btn block" type="button" data-act="show-login">بازگشت</button>
    </form></div>`;
  }
  if (state.authView === "reset") {
    const recovery = state.recovery || {};
    return `<div class="auth"><form class="card auth-card" data-act="reset">
      <div class="brand"><div class="mark">${logo()}</div><div><strong>بازیابی رمز</strong><span>دفترچی</span></div></div>
      ${authProblem()}
      <p class="hint">${recovery.delivery === "internal" ? "سامانه بیرونی فعال نیست؛ کد داخل خود سیستم ساخته شد." : "کد ارسال شد."} ${esc(recovery.detail || "")}</p>
      ${recovery.code ? `<p><strong class="num">${esc(recovery.code)}</strong></p>` : ""}
      <input type="hidden" name="ident" value="${esc(recovery.ident || "")}">
      <div class="field"><label>کد ۶ رقمی</label><input class="ltr" name="code" value="${esc(recovery.code || "")}" required></div>
      <div class="field"><label>رمز جدید</label><input type="password" name="password" minlength="6" required></div>
      <button class="btn primary block" type="submit">ثبت رمز جدید</button>
      <button class="btn block" type="button" data-act="show-login">بازگشت</button>
    </form></div>`;
  }
  if (state.authView === "forgot") {
    return `<div class="auth"><form class="card auth-card" data-act="forgot">
      <div class="brand"><div class="mark">${logo()}</div><div><strong>فراموشی رمز</strong><span>با جیمیل یا موبایل</span></div></div>
      ${authProblem()}
      <p class="hint">اگر جیمیل بدهید، کد بازیابی از هاست وب‌بیکری به همان جیمیل می‌رود.</p>
      <div class="field"><label>موبایل یا جیمیل</label><input name="ident" required value="${esc(draft.ident || "")}"></div>
      <button class="btn primary block" type="submit">دریافت کد</button>
      <button class="btn block" type="button" data-act="show-login">بازگشت</button>
    </form></div>`;
  }
  const initial = state.bootstrap?.initial
    ? `<p class="hint">ورود اولیه: <span class="ltr">${esc(state.bootstrap.phone)}</span> / ${esc(state.bootstrap.password)}</p>`
    : "";
  return `<div class="auth"><form class="card auth-card" data-act="login">
    <div class="brand"><div class="mark">${logo()}</div><div><strong>دفترچی</strong><span>صندوق و حسابداری فروشگاه</span></div></div>
    ${authProblem()}
    <div class="field"><label>موبایل یا جیمیل</label><input name="ident" autocomplete="username" required value="${esc(draft.ident || (state.bootstrap?.initial ? state.bootstrap.phone : ""))}"></div>
    <div class="field"><label>رمز</label><input type="password" name="password" autocomplete="current-password" required value="${esc(draft.password || "")}"></div>
    <button class="btn primary block" type="submit">ورود</button>
    <button class="btn block" type="button" data-act="show-register">ساخت حساب با جیمیل</button>
    <button class="btn block" type="button" data-act="show-forgot">رمز را فراموش کرده‌ام</button>
    ${updateBanner()}
    ${initial}
    <p class="hint">نسخه ${esc(state.bootstrap?.version || state.update?.current || "")}</p>
  </form></div>`;
}
function logo() {
  return `<svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true"><rect x="6" y="4" width="20" height="24" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4v24M16 12h6M16 17h6" stroke="currentColor" stroke-width="2"/></svg>`;
}
function shopBrand() {
  return {
    name: state.shop?.name || state.settings?.shop_name || "دفترچی",
    logo: state.shop?.logo || state.settings?.shop_logo || "",
  };
}
function invoiceSeal(big) {
  const logoUrl = shopBrand().logo;
  if (logoUrl) return `<img class="seal ${big ? "big" : ""}" src="${esc(logoUrl)}" alt="">`;
  return `<span class="seal ${big ? "big" : ""}">${logo()}</span>`;
}
function invoiceSeals(count) {
  return Array.from({ length: count }, () => invoiceSeal(false)).join("");
}
function receiptHtml(modal) {
  const sale = modal.sale;
  const shop = shopBrand();
  const moadianLabel = { skipped: "شناسه کالا ندارد", failed: "ارسال نشد", sent: "در صف سامانه", pending: "در حال بررسی", success: "تأیید شد" }[sale.moadian_status] || "";
  const rows = modal.items.map((item) => `<tr><td>${esc(item.name)} × ${num(item.qty)}</td><td class="num">${money(item.line_total)}</td></tr>`).join("");
  return `<div id="print-area" class="invoice">
    <div class="invoice-edge">${invoiceSeals(6)}</div>
    <div class="invoice-middle">
      <div class="invoice-edge side">${invoiceSeals(4)}</div>
      <div class="invoice-sheet">
        <header class="invoice-head">
          <div class="invoice-brand">${invoiceSeal(true)}<div><strong>${esc(shop.name)}</strong><span class="ltr">webakery.ir</span></div></div>
          <div class="invoice-meta"><b>فاکتور ${num(sale.id)}</b><span>${esc(sale.at_jalali || "")}</span></div>
        </header>
        <p class="invoice-buyer">${esc(sale.customer_name || "")} <span class="ltr">${esc(sale.customer_phone || "")}</span></p>
        <table><thead><tr><th>کالا</th><th>مبلغ</th></tr></thead><tbody>${rows}</tbody></table>
        ${sale.discount ? `<p class="invoice-line"><span>تخفیف</span><span class="num">${money(sale.discount)}</span></p>` : ""}
        <p class="invoice-total"><span>قابل پرداخت</span><span class="num">${money(sale.payable)}</span></p>
        <p class="invoice-pay">${PAY[sale.payment_method] || ""}</p>
        ${sale.moadian_taxid ? `<p class="invoice-tax ltr">${esc(sale.moadian_taxid)}</p>` : ""}
        <p class="invoice-thanks">با تشکر از خرید شما</p>
      </div>
      <div class="invoice-edge side">${invoiceSeals(4)}</div>
    </div>
    <div class="invoice-edge">${invoiceSeals(6)}</div>
  </div>
  ${modal.sms?.detail ? `<p class="hint">${esc(modal.sms.detail)}</p>` : ""}
  ${moadianLabel ? `<p class="hint">سامانه مودیان: ${esc(moadianLabel)}</p>` : ""}
  ${sale.moadian_error ? `<p class="hint">${esc(sale.moadian_error)}</p>` : ""}
  <div class="row-actions"><button type="button" class="btn" data-act="print">چاپ</button>${sale.moadian_status === "success" ? "" : `<button type="button" class="btn primary" data-act="moadian-send" data-id="${sale.id}">ارسال به سامانه مودیان</button>`}${sale.moadian_reference ? `<button type="button" class="btn" data-act="moadian-inquiry" data-id="${sale.id}">استعلام مودیان</button>` : ""}</div>`;
}
function visibleNav(list) {
  return list.filter((item) => item[2] !== "admin" || isAdmin());
}
function tabButton([id, title]) {
  return `<button type="button" class="tab" data-act="nav" data-page="${id}">${title}</button>`;
}
function brandMark() {
  const url = shopBrand().logo;
  if (url) return `<img src="${esc(url)}" alt="">`;
  return logo();
}
function webShell() {
  return `<div class="webapp" data-user="${state.user.id}">
    <header class="apphead">
      <div class="appbar">
        <div class="brand"><div class="mark">${brandMark()}</div><strong>دفترچی</strong></div>
        <div class="top-actions" id="app-status"></div>
      </div>
      <nav class="tabbar" aria-label="بخش‌ها">${visibleNav(NAV).map(tabButton).join("")}</nav>
    </header>
    <div id="banner-host"></div>
    <main class="stage" id="view"></main>
    <div id="support-host"></div>
    <div id="modal-host"></div>
  </div>`;
}
function paintChrome() {
  const mark = document.querySelector(".appbar .mark");
  if (mark) mark.innerHTML = brandMark();
  document.querySelectorAll(".tab[data-page]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.page === state.page);
  });
  const open = state.registerInfo?.open;
  const pill = state.registerInfo
    ? `<span class="pill ${open ? "" : "warn"}">${open ? "صندوق باز" : "صندوق بسته"}</span>`
    : "";
  const access = state.access;
  const accessPill = access
    ? `<span class="pill ${access.active ? "" : "warn"}">${access.mode === "paid" ? "لایسنس فعال" : access.active ? `${num(access.days_left)} روز رایگان` : "مهلت رایگان تمام شد"}</span>`
    : "";
  const status = document.getElementById("app-status");
  if (status) status.innerHTML = `${accessPill}${pill}<button type="button" class="btn" data-act="password-modal">رمز</button><button type="button" class="btn" data-act="logout">خروج</button>`;
  const banner = document.getElementById("banner-host");
  if (banner) {
    banner.innerHTML = [
      state.mustChange ? `<div class="banner">رمز اولیه هنوز فعال است. <button type="button" class="btn" data-act="password-modal">عوضش کنید</button></div>` : "",
      updateBanner(),
    ].join("");
  }
  const modal = document.getElementById("modal-host");
  if (modal) modal.innerHTML = modalHtml();
  const support = document.getElementById("support-host");
  if (support) support.innerHTML = supportHtml();
}

function bars(summary) {
  const max = Math.max(1, ...summary.points.map((point) => point.total));
  return `<div class="bars">${summary.points.map((point) => {
    const height = Math.round((point.total / max) * 100);
    const label = summary.range === "day" && Number(point.label) % 3 !== 0
      ? ""
      : (typeof point.label === "number" ? num(point.label) : esc(point.label));
    return `<div class="bar" title="${esc(money(point.total))}"><i style="height:${height}%"></i><span>${label}</span></div>`;
  }).join("")}</div>`;
}
function salesTable(rows) {
  if (!rows.length) return `<p class="empty">هنوز فروشی ثبت نشده.</p>`;
  return `<table><thead><tr><th>فاکتور</th><th>زمان</th><th>خریدار</th><th>روش</th><th>مبلغ</th></tr></thead><tbody>
    ${rows.map((sale) => `<tr><td class="num">${num(sale.id)}</td><td>${esc(sale.at_jalali)}</td><td>${esc(sale.customer_name || "—")}</td><td>${PAY[sale.payment_method] || ""}</td><td class="num">${money(sale.payable)}</td></tr>`).join("")}
  </tbody></table>`;
}
function dashboardHtml() {
  const data = state.dashboard;
  const summary = data[state.chart];
  const cards = ["day", "week", "month"].map((key) => {
    const labels = { day: "امروز", week: "این هفته", month: "این ماه" };
    return `<button type="button" class="stat ${state.chart === key ? "active" : ""}" data-act="chart" data-range="${key}"><small>${labels[key]}</small><strong class="num">${money(data[key].total)}</strong><span>${num(data[key].count)} فاکتور</span></button>`;
  }).join("");
  const top = summary.top.length
    ? `<ul>${summary.top.map((item) => `<li>${esc(item.name)} — ${num(item.qty)} عدد — ${money(item.total)}</li>`).join("")}</ul>`
    : `<p class="empty">در این بازه فروشی نیست.</p>`;
  return `<div class="stack"><div class="stats">${cards}</div>
    <section class="card"><h2 class="section-title">${esc(summary.label)}</h2>${bars(summary)}<h3 class="section-title">کالاهای پرفروش</h3>${top}</section>
    <section class="card"><h2 class="section-title">آخرین فروش‌ها</h2>${salesTable(state.sales)}</section></div>`;
}

function productHaystack(product) {
  const extra = (product.variations || []).map((item) => `${item.label} ${item.sku} ${item.barcode}`).join(" ");
  return `${product.name} ${product.barcode} ${product.sku} ${product.tax_code || ""} ${extra}`;
}
function stampProducts(rows) {
  rows.forEach((product) => { product.hay = productHaystack(product); });
  return rows;
}
function moreControl(act, total, limit) {
  if (total <= limit) return "";
  const next = Math.min(PAGE_SIZE, total - limit);
  return `<p class="more-rows"><button type="button" class="btn" data-act="${act}">نمایش ${num(next)} تای بعدی · ${num(limit)} از ${num(total)}</button></p>`;
}
function variationLines(product) {
  if (product.type !== "variable" || !product.variations?.length) return "";
  return `<div class="var-list">${product.variations.map((item) => `<div class="var-line"><span>${esc(item.label)}</span><span class="num">${item.tracked ? `موجودی ${num(item.stock)}` : (item.in_stock ? "موجود" : "ناموجود")}</span><span class="num">${money(item.price)}</span></div>`).join("")}</div>`;
}
function stockChoices(products) {
  return products.map((product) => {
    if (product.type === "variable" && product.variations?.length) {
      return product.variations.map((item) => `<option value="${product.id}:${item.id}">${esc(product.name)} — ${esc(item.label)}</option>`).join("");
    }
    return `<option value="${product.id}">${esc(product.name)}</option>`;
  }).join("");
}
function posTiles() {
  const query = state.posQuery.trim();
  const rows = state.products.filter((product) => !query || (product.hay || productHaystack(product)).includes(query));
  if (!rows.length) return `<p class="empty">کالایی پیدا نشد.</p>`;
  const shown = rows.slice(0, state.posLimit);
  return `<div class="product-grid">${shown.map((product) => {
    const variable = product.type === "variable" && product.variations?.length;
    const sellable = variable ? product.variations.some((item) => item.in_stock) : product.stock > 0;
    const price = variable ? `از ${money(product.price)}` : money(product.price);
    const stock = variable ? `${num(product.variations.length)} نوع` : `موجودی ${num(product.stock)}`;
    return `<button type="button" class="tile" data-act="add-cart" data-id="${product.id}" ${sellable ? "" : "disabled"}>
    ${thumb(product.image, product.name)}
    <span class="pname">${esc(product.name)}</span>
    <span class="num">${price}</span>
    <span class="pstock">${stock}${product.low ? " · کم" : ""}</span>
  </button>`;
  }).join("")}</div>${moreControl("more-pos", rows.length, state.posLimit)}`;
}
function posHtml() {
  const subtotal = cartSubtotal();
  const discount = cartDiscount();
  const payable = subtotal - discount;
  const closed = state.registerInfo && !state.registerInfo.open;
  const lines = state.cart.length ? state.cart.map((line) => `<div class="line"><div><strong>${esc(line.name)}</strong><div class="muted num">${money(line.price)}</div></div>
    <div><div class="qty"><button type="button" data-act="dec" data-id="${line.id}" data-variation="${line.variationId || 0}">−</button><span class="num">${num(line.qty)}</span><button type="button" data-act="inc" data-id="${line.id}" data-variation="${line.variationId || 0}">+</button></div>
    <button type="button" class="btn danger" data-act="remove-line" data-id="${line.id}" data-variation="${line.variationId || 0}">حذف</button></div></div>`).join("") : `<p class="empty">سبد خالی است. بارکد را بخوانید یا کالا را انتخاب کنید.</p>`;
  const pending = state.pending.length ? `<div><h3 class="section-title">پرداخت‌های باز</h3>${state.pending.map((sale) => `<div class="line"><span>فاکتور ${num(sale.id)} · ${money(sale.payable)}</span><button type="button" class="btn" data-act="open-gateway" data-id="${sale.id}">ادامه</button></div>`).join("")}</div>` : "";
  return `<div class="pos">
    <section class="card cart">
      ${closed ? `<div class="banner">صندوق بسته است. <button type="button" class="btn" data-act="nav" data-page="register">باز کردن صندوق</button></div>` : ""}
      <div class="field"><label>بارکدخوان</label><input id="barcode" data-barcode="1" class="ltr" autocomplete="off" placeholder="بارکد را اینجا بگیرید"></div>
      ${lines}
      <div class="grid-2">
        <div class="field"><label>تخفیف</label><input id="discount" value="${esc(state.discountValue)}" inputmode="numeric"></div>
        <div class="field"><label>نوع</label><select id="discount-type"><option value="amount" ${state.discountType === "amount" ? "selected" : ""}>مبلغ</option><option value="percent" ${state.discountType === "percent" ? "selected" : ""}>درصد</option></select></div>
      </div>
      <div class="grid-2">
        <div class="field"><label>نام</label><input id="buyer-first" value="${esc(state.buyerFirst)}" autocomplete="off"></div>
        <div class="field"><label>نام خانوادگی</label><input id="buyer-last" value="${esc(state.buyerLast)}" autocomplete="off"></div>
      </div>
      <div class="field"><label>شماره موبایل</label><input id="buyer-phone" class="ltr" value="${esc(state.buyerPhone)}" inputmode="tel" autocomplete="off" placeholder="09..."></div>
      <p class="hint">خرید حضوری بدون نام، نام خانوادگی و موبایل تمام نمی‌شود. پیامک ثبت خرید به همین شماره می‌رود.</p>
      <p>جمع <strong class="num" id="pay-sub">${money(subtotal)}</strong></p>
      <p>تخفیف <strong class="num" id="pay-disc">${money(discount)}</strong></p>
      <p>قابل پرداخت <strong class="num" id="pay-due">${money(payable)}</strong></p>
      <div class="pay-row">
        <button type="button" class="btn primary" data-act="pay" data-method="cash">نقد</button>
        <button type="button" class="btn" data-act="pay" data-method="card">کارت‌خوان</button>
        <button type="button" class="btn" data-act="pay" data-method="gateway">درگاه</button>
        <button type="button" class="btn" data-act="pay" data-method="credit">نسیه</button>
      </div>
      ${pending}
    </section>
    <section class="stack">
      <input id="pos-query" value="${esc(state.posQuery)}" placeholder="جستجوی نام، کد یا بارکد">
      <div id="pos-grid">${posTiles()}</div>
    </section>
  </div>`;
}

function productRows() {
  const query = state.productQuery.trim();
  const rows = state.products.filter((product) => !query || (product.hay || productHaystack(product)).includes(query));
  if (!rows.length) return `<p class="empty">کالایی در این فهرست نیست.</p>`;
  const shown = rows.slice(0, state.productLimit);
  return `<table><thead><tr><th></th><th>نام</th><th>بارکد</th><th>مودیان</th><th>قیمت فروش</th><th>موجودی</th><th></th></tr></thead><tbody>
    ${shown.map((product) => `<tr><td>${thumb(product.image, product.name, true)}</td><td>${esc(product.name)}${product.woo_id ? ` <span class="pill">ووکامرس</span>` : ""}${product.type === "variable" ? ` <span class="pill">متغیر</span>` : ""}${variationLines(product)}</td><td class="ltr">${esc(product.barcode || "—")}</td><td class="ltr">${esc(product.tax_code || "—")}</td><td class="num">${product.type === "variable" ? `از ${money(product.price)}` : money(product.price)}</td><td class="num">${num(product.stock)} ${product.low ? `<span class="pill warn">کم</span>` : ""}</td><td class="row-actions"><button type="button" class="btn" data-act="edit-product" data-id="${product.id}">ویرایش</button><button type="button" class="btn danger" data-act="archive-product" data-id="${product.id}">بایگانی</button></td></tr>`).join("")}
  </tbody></table>${moreControl("more-products", rows.length, state.productLimit)}`;
}
function productsHtml() {
  const imported = state.importResult;
  const banner = imported ? `<div class="banner">از اکسل ${num(imported.created)} کالا ثبت و ${num(imported.updated)} کالا به‌روز شد.
    ${imported.ids?.length ? `<button type="button" class="btn" data-act="woo-push-ids">ارسال همین‌ها به ووکامرس</button>` : ""}
    ${imported.errors?.length ? `<div>${imported.errors.map((row) => `<div>ردیف ${num(row.row)}: ${esc(row.error)}</div>`).join("")}</div>` : ""}
  </div>` : "";
  return `<div class="stack">${banner}
    <section class="card"><div class="row-actions">
      <button type="button" class="btn primary" data-act="new-product">کالای جدید</button>
      <a class="btn" href="/api/products/template">نمونه اکسل</a>
      <button type="button" class="btn" data-act="open-import">ورود با اکسل</button>
      <button type="button" class="btn" data-act="woo-push">ارسال همه به ووکامرس</button>
      <button type="button" class="btn" data-act="woo-pull">دریافت از ووکامرس</button>
    </div><p class="hint">ستون‌های اکسل: نام کالا، SKU، موجودی، قیمت فروش.</p></section>
    <section class="card"><input id="product-query" value="${esc(state.productQuery)}" placeholder="جستجو"><div id="product-table">${productRows()}</div></section>
  </div>`;
}

function inventoryFiltered() {
  const products = state.inventory?.products || [];
  const query = state.inventoryQuery.trim();
  if (!query) return products;
  return products.filter((product) => `${product.name} ${product.sku || ""} ${product.barcode || ""}`.includes(query));
}
function inventoryTable() {
  const rows = inventoryFiltered();
  const shown = rows.slice(0, state.inventoryLimit);
  const body = shown.map((product) => `<tr><td>${thumb(product.image, product.name, true)}</td><td>${esc(product.name)}${product.type === "variable" ? ` <span class="pill">متغیر</span>` : ""}${variationLines(product)}</td><td class="num">${money(product.price)}</td><td class="num">${money(product.cost)}</td><td class="num">${num(product.stock)} ${product.low ? `<span class="pill warn">کم</span>` : ""}</td></tr>`).join("") || `<tr><td colspan="5">کالایی نیست.</td></tr>`;
  return `<table><thead><tr><th></th><th>کالا</th><th>قیمت</th><th>خرید</th><th>موجودی</th></tr></thead><tbody>${body}</tbody></table>${moreControl("more-inventory", rows.length, state.inventoryLimit)}`;
}
function inventoryHtml() {
  const data = state.inventory;
  if (!data) return "";
  const options = stockChoices(inventoryFiltered().slice(0, PAGE_SIZE));
  const pay = data.pay_accounts.map((account) => `<option value="${esc(account.code)}">${esc(account.name)}</option>`).join("");
  return `<div class="stack"><section class="card"><input id="inventory-query" value="${esc(state.inventoryQuery)}" placeholder="جستجوی کالا برای دیدن و تعدیل"><div id="inventory-box">${inventoryTable()}</div>
    <details><summary>تعدیل موجودی</summary><form data-act="adjust"><div class="field"><label>کالا</label><select name="product_id">${options}</select><p class="hint">اگر کالا در فهرست نیست، نامش را بالا بنویسید.</p></div><div class="field"><label>موجودی جدید</label><input name="stock" inputmode="numeric" required></div><div class="field"><label>شرح</label><input name="note"></div><button class="btn primary" type="submit">ثبت</button></form></details>
    <details><summary>رسید خرید</summary><form data-act="purchase"><div class="grid-2"><div class="field"><label>کالا</label><select name="product_id">${options}</select></div><div class="field"><label>تعداد</label><input name="qty" inputmode="numeric" required></div></div><div class="grid-2"><div class="field"><label>فی خرید</label><input name="unit_cost" inputmode="numeric" required></div><div class="field"><label>پرداخت از</label><select name="pay_code">${pay}</select></div></div><p class="hint">اگر فی خرید وارد شود، میانگین قیمت خرید عوض می‌شود و سند حسابداری می‌خورد.</p><button class="btn primary" type="submit">ثبت خرید</button></form></details>
  </section>
  <section class="card"><h2 class="section-title">گردش اخیر</h2><table><thead><tr><th>زمان</th><th>کالا</th><th>نوع</th><th>از</th><th>به</th><th>شرح</th></tr></thead><tbody>
    ${data.logs.map((row) => `<tr><td>${esc(row.at_jalali)}</td><td>${esc(row.product_name)}</td><td>${KINDS[row.kind] || esc(row.kind)}</td><td class="num">${num(row.old_value)}</td><td class="num">${num(row.new_value)}</td><td>${esc(row.note || "")}</td></tr>`).join("") || `<tr><td colspan="6">گردشی نیست.</td></tr>`}
  </tbody></table></section></div>`;
}

function accountsHtml() {
  const data = state.accounts;
  if (!data) return "";
  const options = data.accounts.map((account) => `<option value="${account.id}">${esc(account.code)} ${esc(account.name)}</option>`).join("");
  return `<div class="stack"><section class="card"><p>جمع بدهکار ${money(data.debit_total)} · جمع بستانکار ${money(data.credit_total)} · ${data.balanced ? "تراز است" : "تراز نیست"}</p>
    <table><thead><tr><th>کد</th><th>حساب</th><th>نوع</th><th>مانده</th><th>سمت</th></tr></thead><tbody>
      ${data.accounts.map((account) => `<tr class="clickable ${String(state.accountId) === String(account.id) ? "selected" : ""}" data-act="filter-account" data-id="${account.id}"><td class="ltr">${esc(account.code)}</td><td>${esc(account.name)}</td><td>${TYPES[account.type] || ""}</td><td class="num">${money(account.amount)}</td><td>${esc(account.side)}</td></tr>`).join("")}
    </tbody></table>
    <details open><summary>سند دستی</summary><form data-act="journal"><div class="field"><label>شرح</label><input name="memo" required></div><div class="grid-2"><div class="field"><label>حساب</label><select name="account_id">${options}</select></div><div class="field"><label>حساب مقابل</label><select name="counter_id">${options}</select></div></div><div class="grid-2"><div class="field"><label>مبلغ</label><input name="amount" inputmode="numeric" required></div><div class="field"><label>این حساب</label><select name="side"><option value="debit">بدهکار شود</option><option value="credit">بستانکار شود</option></select></div></div><button class="btn primary" type="submit">ثبت سند</button></form></details>
    <details><summary>حساب جدید</summary><form data-act="create-account"><div class="field"><label>نام</label><input name="name" required></div><div class="grid-2"><div class="field"><label>نوع</label><select name="type"><option value="person">شخص</option><option value="asset">دارایی</option><option value="liability">بدهی</option><option value="equity">سرمایه</option><option value="income">درآمد</option><option value="expense">هزینه</option></select></div><div class="field"><label>مانده اول</label><input name="opening" inputmode="numeric" value="0"></div></div><div class="field"><label>سمت مانده اول</label><select name="opening_side"><option value="debit">بدهکار</option><option value="credit">بستانکار</option></select></div><button class="btn primary" type="submit">ساخت حساب</button></form></details>
  </section>
  <section class="card"><div class="row-actions"><h2 class="section-title">اسناد</h2><button type="button" class="btn" data-act="filter-account" data-id="">همه</button></div>
    ${state.journal.map((entry) => `<article><strong>${esc(entry.memo || "سند")}</strong> <span class="muted">${esc(entry.at_jalali)}</span><table>${entry.lines.map((line) => `<tr><td>${esc(line.code)} ${esc(line.name)}</td><td class="num">${line.debit ? money(line.debit) : ""}</td><td class="num">${line.credit ? money(line.credit) : ""}</td></tr>`).join("")}</table></article>`).join("") || `<p class="empty">سندی نیست.</p>`}
  </section></div>`;
}

function figuresHtml(figures) {
  const rows = [
    ["موجودی اول", figures.opening], ["فروش نقد", figures.cash_sales], ["فروش کارت", figures.card_sales],
    ["فروش درگاه", figures.gateway_sales], ["فروش نسیه", figures.credit_sales],
    ["دریافت طلب", figures.cash_receipts], ["خرید نقدی", figures.cash_purchases], ["مورد انتظار", figures.expected_cash],
  ];
  return `<table>${rows.map(([label, value]) => `<tr><th>${label}</th><td class="num">${money(value)}</td></tr>`).join("")}</table>`;
}
function registerHtml() {
  const info = state.registerInfo;
  if (!info) return "";
  const session = info.session;
  const history = info.history || [];
  const body = session ? `<section class="card"><h2 class="section-title">نوبت ${num(session.id)} از ${esc(session.opened_jalali)}</h2>${figuresHtml(session.figures)}
      <form data-act="close-register"><div class="field"><label>پول شمارش‌شده در کشو</label><input name="counted_cash" inputmode="numeric" value="${session.figures.expected_cash}"></div>
      <button class="btn primary" type="submit">بستن صندوق</button></form>
      <p class="hint">اختلاف شمارش با موجودی مورد انتظار در حساب کسر و اضافه ثبت می‌شود و برای مدیر پیامک می‌رود اگر در تنظیمات روشن باشد.</p></section>`
    : `<section class="card"><form data-act="open-register"><div class="field"><label>موجودی اول کشو</label><input name="opening_cash" inputmode="numeric" value="${info.suggested_opening}"></div>
      <p class="hint">پیشنهاد از مانده دفتری صندوق است. اگر عدد را عوض کنید، اختلاف به‌عنوان آورده یا برداشت سرمایه ثبت می‌شود.</p>
      <button class="btn primary" type="submit">باز کردن صندوق</button></form></section>`;
  const past = `<section class="card"><h2 class="section-title">نوبت‌های قبل</h2>${history.length ? `<table><thead><tr><th>شروع</th><th>پایان</th><th>مورد انتظار</th><th>شمارش</th><th>اختلاف</th></tr></thead><tbody>
    ${history.map((row) => `<tr><td>${esc(row.opened_jalali)}</td><td>${esc(row.closed_jalali)}</td><td class="num">${money(row.figures.expected_cash)}</td><td class="num">${money(row.counted_cash)}</td><td class="num">${money(row.figures.difference)}</td></tr>`).join("")}
  </tbody></table>` : `<p class="empty">هنوز صندوقی بسته نشده.</p>`}</section>`;
  return `<div class="stack">${body}${past}</div>`;
}

function accessCard(access) {
  if (!access) return "";
  if (access.mode === "paid" && access.active) {
    return `<section class="card access-card"><span>لایسنس این دفترچی</span><h2>${esc(access.title)}</h2><p class="days">${num(access.days_left)} روز مانده</p><p class="hint">تا ${esc(access.ends_jalali)}</p></section>`;
  }
  if (access.active) {
    return `<section class="card access-card"><span>استفاده رایگان</span><h2>۷ روز رایگان فعال است</h2><p class="days">${num(access.days_left)} روز مانده</p><p class="hint">تا ${esc(access.ends_jalali)}. هر وقت خواستید روی یک طرح بزنید.</p></section>`;
  }
  return `<section class="card access-card"><span>مهلت رایگان</span><h2>۷ روز رایگان تمام شده</h2><p class="hint">برای ادامه کار، روی یکی از طرح‌ها بزنید. صفحه زیبال باز می‌شود.</p></section>`;
}
function licensesHtml() {
  const data = state.licenses;
  if (!data) return "";
  const plans = data.plans.map((plan) => `<button type="button" class="plan buy" data-act="pick-plan" data-plan="${plan.id}"><span>${esc(plan.title)}</span><em class="num">${money(plan.price)}</em><span class="buy-label">خرید</span>${plan.remaining != null ? `<span>باقی‌مانده ${num(plan.remaining)} از ${num(plan.cap)}</span>` : ""}</button>`).join("");
  return `<div class="stack">${accessCard(data.access)}<div class="plans">${plans}</div>
    <p class="hint">روی طرح بزنید تا صفحه زیبال باز شود. مبلغ وارد صندوق فروشگاه نمی‌شود. نام، موبایل و طرح خریدار روی هاست وب‌بیکری هم می‌ماند؛ فایل accounts.php را کنار pay.php در public_html/license-server بگذارید.</p>
      <details><summary>قیمت‌ها و ظرفیت پنجاه‌ساله</summary><form data-act="save-prices"><div class="grid-2">
        ${[["price_3m", "سه ماهه"], ["price_6m", "شش ماهه"], ["price_12m", "یک ساله"], ["price_50y", "پنجاه ساله"], ["cap_50y", "ظرفیت پنجاه ساله"]].map(([key, label]) => {
          const plan = data.plans.find((item) => item.id === { price_3m: "3m", price_6m: "6m", price_12m: "12m", price_50y: "50y" }[key]);
          const value = key === "cap_50y" ? (data.plans.find((item) => item.id === "50y")?.cap ?? 50) : (plan?.price ?? "");
          return `<div class="field"><label>${label}</label><input name="${key}" value="${value}"></div>`;
        }).join("")}
      </div><button class="btn" type="submit">ذخیره قیمت‌ها</button></form></details>
    ${pendingLicenses(data)}
    <section class="card"><h2 class="section-title">لایسنس‌های فروخته‌شده</h2><table><thead><tr><th>طرح</th><th>خریدار</th><th>تماس</th><th>مبلغ</th><th>وضعیت</th><th>هاست</th><th>تا</th></tr></thead><tbody>
      ${data.licenses.map((row) => `<tr><td>${esc(row.title)}</td><td>${esc(row.buyer_name)}</td><td class="ltr">${esc(row.phone)}</td><td class="num">${money(row.payable)}</td><td>${esc(LICENSE_STATUS[row.status] || row.status)}</td><td>${row.host_saved ? "ذخیره شد" : "منتظر هاست"}</td><td>${esc(row.ends_jalali)}</td></tr>`).join("") || `<tr><td colspan="7">هنوز لایسنسی فروخته نشده.</td></tr>`}
    </tbody></table></section></div>`;
}

function pendingLicenses(data) {
  const rows = (data.licenses || []).filter((row) => row.status === "pending");
  if (!rows.length) return "";
  return `<section class="card"><h2 class="section-title">پرداخت‌های باز وب‌بیکری</h2>${rows.map((row) => `<div class="line"><span>${esc(row.title)} · ${esc(row.buyer_name)} · ${money(row.payable)}</span><button type="button" class="btn" data-act="open-license" data-id="${row.id}">ادامه</button></div>`).join("")}</section>`;
}

function customersHtml() {
  const debtors = state.customers.filter((row) => row.balance > 0 && row.account_id);
  return `<div class="stack"><section class="card">${debtors.length && isAdmin() ? `<form data-act="receipt"><div class="grid-2"><div class="field"><label>مشتری بدهکار</label><select name="account_id">${debtors.map((row) => `<option value="${row.account_id}">${esc(row.name)} — ${money(row.balance)}</option>`).join("")}</select></div><div class="field"><label>مبلغ</label><input name="amount" inputmode="numeric" required></div></div><div class="field"><label>روش</label><select name="payment_method"><option value="cash">نقد</option><option value="card">کارت</option></select></div><button class="btn primary" type="submit">دریافت طلب</button></form>` : `<p class="empty">مانده نسیه‌ای برای دریافت نیست.</p>`}</section>
    <section class="card"><table><thead><tr><th>نام</th><th>تماس</th><th>خرید</th><th>مانده</th><th>سمت</th></tr></thead><tbody>
      ${state.customers.map((row) => `<tr><td>${esc(row.name)}</td><td class="ltr">${esc(row.phone)}</td><td class="num">${num(row.purchases)}</td><td class="num">${money(row.amount)}</td><td>${esc(row.side)}</td></tr>`).join("") || `<tr><td colspan="5">هنوز مشتری‌ای ثبت نشده.</td></tr>`}
    </tbody></table></section></div>`;
}

function smsHtml() {
  return `<div class="stack"><section class="card"><form data-act="send-sms"><div class="field"><label>شماره مدیر یا گیرنده</label><input class="ltr" name="recipient" required placeholder="09..."></div><div class="field"><label>متن</label><textarea name="body" required></textarea></div><button class="btn primary" type="submit">ارسال</button><p class="hint">اگر کاوه‌نگار یا ملی‌پیامک تنظیم نشده باشد، پیام در همین صندوق می‌ماند.</p></form></section>
    <section class="card"><table><thead><tr><th>زمان</th><th>گیرنده</th><th>متن</th><th>وضعیت</th></tr></thead><tbody>
      ${state.sms.map((row) => `<tr><td>${esc(row.at_jalali)}</td><td class="ltr">${esc(row.recipient)}</td><td>${esc(row.body)}</td><td>${esc(row.status)} ${esc(row.detail || "")}</td></tr>`).join("") || `<tr><td colspan="4">پیامی نیست.</td></tr>`}
    </tbody></table></section></div>`;
}

function options(pairs, current) {
  return pairs.map(([value, label]) => `<option value="${value}" ${value === current ? "selected" : ""}>${label}</option>`).join("");
}
function field(key, label, type = "text", placeholder = "") {
  const hold = placeholder ? ` placeholder="${esc(placeholder)}"` : "";
  return `<div class="field"><label>${label}</label><input name="${key}" type="${type}" value="${esc(state.settings[key] || "")}"${hold} ${type === "text" && /url|host|phone|sender|key|user|merchant|callback|chat/.test(key) ? `class="ltr"` : ""}></div>`;
}
function settingsHtml() {
  const s = state.settings;
  if (!s) return "";
  const checked = (key) => s[key] === "1" ? "checked" : "";
  return `<form class="stack" data-act="save-settings">
    <section class="card"><h2 class="section-title">سربرگ فاکتور</h2>
      ${field("shop_name", "نام فروشگاه روی فاکتور")}
      <input type="hidden" name="shop_logo" value="${esc(s.shop_logo || "")}">
      <div class="field"><label>لوگوی سایت</label><input type="file" name="logo_file" accept="image/*"></div>
      ${s.shop_logo ? `<img class="logo-preview" src="${esc(s.shop_logo)}" alt="">` : ""}
      <label class="check"><input type="checkbox" name="clear_shop_logo">برداشتن لوگو و برگشت به نشان دفترچی</label>
      <p class="hint">لوگو دور فاکتور و بالای آن می‌نشیند. لوگوی سایت را همین‌جا بگذارید. اگر خالی بماند، نشان دفترچی چاپ می‌شود.</p>
    </section>
    <section class="card"><h2 class="section-title">وردپرس و ووکامرس</h2>
      ${field("wp_url", "آدرس سایت")}${field("woo_key", "Consumer key", "text", "ck_...")}${field("woo_secret", "Consumer secret", "password", "cs_...")}
      <div class="row-actions"><button type="button" class="btn" data-act="test-setting" data-kind="wp">آزمایش وردپرس</button><button type="button" class="btn" data-act="test-setting" data-kind="woo">آزمایش ووکامرس</button></div>
      <p class="hint">آدرس همان صفحه فروشگاه است، مثل https://aquasafe.ir. دکمه آزمایش همین مقدارهای نوشته‌شده را می‌زند. کلید را از ووکامرس، تنظیمات، پیشرفته، REST API با کاربر مدیر بسازید و دسترسی را خواندن و نوشتن بگذارید. کادر Consumer key باید پر باشد و با ck_ شروع شود.</p>
    </section>
    <section class="card"><h2 class="section-title">کارت‌خوان ایرانی</h2>
      <div class="field"><label>شرکت</label><select name="pos_provider">${options([["manual", "دستی"], ["saman", "سامان کیش"], ["behpardakht", "به‌پرداخت ملت"], ["parsian", "پارسیان"], ["irankish", "ایران‌کیش"], ["sepehr", "سپهر"], ["asanpardakht", "آسان‌پرداخت"]], s.pos_provider)}</select></div>
      <div class="grid-2">${field("pos_host", "آدرس یا IP")}${field("pos_port", "پورت")}</div>
      ${field("pos_terminal", "شماره پایانه")}
      <button type="button" class="btn" data-act="test-setting" data-kind="pos">آزمایش اتصال</button>
      <p class="hint">اگر دستگاه وصل باشد ارتباط شبکه آزمایش می‌شود. پروتکل اختصاصی هر شرکت در خود دستگاه می‌ماند و شماره پیگیری رسید را موقع فروش وارد می‌کنید.</p>
    </section>
    <section class="card"><h2 class="section-title">درگاه پرداخت</h2>
      <div class="field"><label>درگاه</label><select name="gateway">${options([["zarinpal", "زرین‌پال"], ["idpay", "آی‌دی‌پی"], ["zibal", "زیبال"]], s.gateway)}</select></div>
      ${field("license_merchant", "مرچنت زیبال لایسنس")}${field("gateway_merchant", "مرچنت فروش کالا")}${field("gateway_callback", "آدرس بازگشت")}
      <label class="check"><input type="checkbox" name="gateway_sandbox" ${checked("gateway_sandbox")}>حالت آزمایشی زرین‌پال برای فروش کالا</label>
      <p class="hint">درگاه پیش‌فرض زیبال است. فروش کالا و لایسنس با مرچنت وب‌بیکری پرداخت می‌شوند. مبلغ تومان است و برای زیبال به ریال تبدیل می‌شود. بازگشت پیش‌فرض https://webakery.ir است.</p>
    </section>
    <section class="card"><h2 class="section-title">پیامک</h2>
      <div class="field"><label>سامانه</label><select name="sms_provider">${options([["internal", "فقط داخل دفترچی"], ["kavenegar", "کاوه‌نگار"], ["melipayamak", "ملی‌پیامک"]], s.sms_provider)}</select></div>
      <div class="grid-2">${field("sms_api_key", "کلید کاوه‌نگار", "password")}${field("sms_sender", "شماره خط")}</div>
      <div class="grid-2">${field("sms_username", "نام کاربری ملی‌پیامک")}${field("sms_password", "رمز ملی‌پیامک", "password")}</div>
      ${field("manager_phone", "موبایل مدیر")}${field("low_stock", "آستانه موجودی کم")}
      <label class="check"><input type="checkbox" name="sms_on_close" ${checked("sms_on_close")}>پیامک بعد از بستن صندوق</label>
      <label class="check"><input type="checkbox" name="sms_on_sale" ${checked("sms_on_sale")}>پیامک هر فروش به مدیر</label>
      <p class="hint">پیامک خرید حضوری جداگانه به موبایل خود خریدار می‌رود، به شرط نام، نام خانوادگی و شماره.</p>
      <label class="check"><input type="checkbox" name="sms_low_stock" ${checked("sms_low_stock")}>پیامک موجودی کم</label>
      <button type="button" class="btn" data-act="test-setting" data-kind="sms">پیام آزمایشی</button>
    </section>
    <section class="card"><h2 class="section-title">سامانه مودیان</h2>
      <div class="grid-2"><div class="field"><label>شناسه یکتای حافظه مالیاتی</label><input class="ltr" name="moadian_fiscal_id" maxlength="6" value="${esc(s.moadian_fiscal_id || "")}"></div><div class="field"><label>کد اقتصادی</label><input class="ltr" name="moadian_economic_code" value="${esc(s.moadian_economic_code || "")}"></div></div>
      <div class="field"><label>کلید خصوصی کارپوشه</label><textarea class="ltr" name="moadian_private_key" rows="4" placeholder="${s.moadian_key_saved === "1" ? "کلید ذخیره شده است. برای عوض کردن، کلید تازه را بچسبانید." : "متن فایل pem"}"></textarea></div>
      ${field("moadian_vat", "نرخ مالیات، درصد")}
      <label class="check"><input type="checkbox" name="moadian_enabled" ${checked("moadian_enabled")}>بعد از هر فروش، صورتحساب به سامانه برود</label>
      <label class="check"><input type="checkbox" name="moadian_sandbox" ${checked("moadian_sandbox")}>ارسال آزمایشی. صورتحساب واقعی ثبت نمی‌شود</label>
      <button type="button" class="btn" data-act="test-setting" data-kind="moadian">آزمایش اتصال</button>
      <p class="hint">شناسه حافظه مالیاتی، کد اقتصادی و کلید خصوصی را از کارپوشه بگیرید. شناسه ۱۳ رقمی کالا/خدمت را روی هر کالا بگذارید. تا وقتی ارسال آزمایشی روشن است، فاکتور به سامانه واقعی نمی‌رود. مبلغ فروش تومان است و برای مودیان به ریال تبدیل می‌شود.</p>
    </section>
    <section class="card"><h2 class="section-title">جیمیل حساب کاربری</h2>
      <button type="button" class="btn" data-act="test-setting" data-kind="email">آزمایش هاست جیمیل</button>
      <p class="hint">کد تأیید و بازیابی رمز از هاست وب‌بیکری به جیمیل می‌رود. فایل mail.php باید در public_html/daftarchi باشد. رمز ورود جیمیل روی این رایانه لازم نیست.</p>
    </section>
    <section class="card"><h2 class="section-title">پشتیبانی تلگرام</h2>
      ${field("telegram_bot_token", "توکن ربات", "password", s.telegram_token_saved === "1" ? "توکن ذخیره شده است" : "123456:ABC...")}
      ${field("telegram_chat_id", "شناسه چت", "text", "عدد چت یا کانال")}
      <p class="hint">ربات را در تلگرام با BotFather بسازید و توکن را اینجا بگذارید. شناسه چت همان عددی است که پیام‌ها باید به آن برسد. اگر این رایانه به تلگرام نرسد، فایل telegram.php و telegram.json را کنار version.json روی هاست بگذارید.</p>
    </section>
    <section class="card"><h2 class="section-title">جای فایل‌های آپدیت</h2>
      <p class="hint">نسخه نصب‌شده: ${esc(state.update?.current || "")}. دفترچی این آدرس را می‌خواند:</p>
      <p class="ltr">https://webakery.ir/daftarchi/version.json</p>
      <p class="hint">این فایل‌ها را از گیت‌هاب دانلود کنید، نه از خود هاست. بعد روی هاست در public_html/daftarchi بگذارید:</p>
      <p class="ltr">https://raw.githubusercontent.com/mohammad-mahdikhani/one-project/cursor/accounting-ledger-56dd/Daftarchi-Host.zip</p>
      <p class="ltr">https://raw.githubusercontent.com/mohammad-mahdikhani/one-project/cursor/accounting-ledger-56dd/Daftarchi.exe</p>
      <p class="hint">زیپ را باز کنید. version.json و mail.php را با فایل نصب در همان پوشه هاست بگذارید.</p>
    </section>
    <button class="btn primary" type="submit">ذخیره تنظیمات</button>
  </form>
  <section class="card" style="margin-top:14px"><h2 class="section-title">ساخت اکانت</h2>
    <table><thead><tr><th>نام</th><th>موبایل</th><th>جیمیل</th><th>نقش</th></tr></thead><tbody>${state.users.map((user) => `<tr><td>${esc(user.name)}</td><td class="ltr">${esc(user.phone)}</td><td class="ltr">${esc(user.email || "—")}${user.email && !user.email_verified ? " · تأیید نشده" : ""}</td><td>${user.role === "admin" ? "مدیر" : "صندوقدار"}</td></tr>`).join("")}</tbody></table>
    <form data-act="create-user"><div class="grid-2"><div class="field"><label>نام</label><input name="name" required></div><div class="field"><label>موبایل</label><input class="ltr" name="phone" required></div></div><div class="grid-2"><div class="field"><label>جیمیل</label><input class="ltr" name="email"></div><div class="field"><label>رمز</label><input type="password" name="password" required></div></div><div class="field"><label>نقش</label><select name="role"><option value="cashier">صندوقدار</option><option value="admin">مدیر</option></select></div><button class="btn primary" type="submit">ساخت کاربر</button></form>
  </section>`;
}

function productForm() {
  const product = state.modal?.product || {};
  const price = product.id ? product.price : "";
  const cost = product.cost ? product.cost : "";
  return `<form data-act="save-product"><h2 class="section-title">${product.id ? "ویرایش کالا" : "کالای جدید"}</h2>
    <input type="hidden" name="id" value="${product.id || ""}">
    <div class="field"><label>نام کالا</label><input name="name" value="${esc(product.name || "")}" required></div>
    <div class="field"><label>قیمت فروش، تومان</label><input name="price" inputmode="decimal" required autocomplete="off" value="${price}" ${product.type === "variable" ? "readonly" : ""}></div>
    ${product.type === "variable" ? `<p class="hint">موجودی و قیمت این کالا از متغیرهای ووکامرس می‌آید و با ویرایش اینجا عوض نمی‌شود.</p>${variationLines(product)}` : `<div class="field"><label>موجودی</label><input name="stock" inputmode="numeric" autocomplete="off" value="${product.id ? product.stock : ""}"></div>`}
    <div class="field"><label>بارکد</label><input class="ltr" name="barcode" autocomplete="off" value="${esc(product.barcode || "")}"></div>
    <div class="field"><label>شناسه کالا/خدمت مودیان</label><input class="ltr" name="tax_code" inputmode="numeric" autocomplete="off" placeholder="۱۳ رقم، اختیاری" value="${esc(product.tax_code || "")}"></div>
    <details ${product.id ? "open" : ""}>
      <summary>کد، قیمت خرید و تصویر</summary>
      <div class="field"><label>کد کالا</label><input name="sku" value="${esc(product.sku || "")}"></div>
      <div class="field"><label>قیمت خرید، تومان</label><input name="cost" inputmode="numeric" placeholder="اختیاری" value="${cost}"></div>
      <div class="field"><label>آدرس تصویر</label><input class="ltr" name="image" value="${esc(product.image || "")}"></div>
      <div class="field"><label>یا بارگذاری تصویر</label><input type="file" name="file" accept="image/*"></div>
      ${product.image ? thumb(product.image, product.name) : ""}
    </details>
    <button class="btn primary" type="submit">ذخیره</button></form>`;
}
function modalHtml() {
  const modal = state.modal;
  if (!modal) return "";
  let inner = "";
  if (modal.type === "product") inner = productForm();
  if (modal.type === "variations") {
    const product = modal.product;
    inner = `<h2 class="section-title">${esc(product.name)}</h2><p class="hint">نوع متغیر را انتخاب کنید. موجودی هر نوع جداست.</p><div class="var-pick">${(product.variations || []).map((item) => `<button type="button" class="btn var-choice" data-act="pick-variation" data-id="${product.id}" data-variation="${item.id}" ${item.in_stock ? "" : "disabled"}><span>${esc(item.label)}</span><span class="num">${item.tracked ? `موجودی ${num(item.stock)}` : (item.in_stock ? "موجود" : "ناموجود")}</span><span class="num">${money(item.price)}</span></button>`).join("")}</div>`;
  }
  if (modal.type === "card") inner = `<h2 class="section-title">کارت‌خوان</h2><p>${esc(modal.message || "")}</p><div class="field"><label>شماره پیگیری رسید</label><input id="pos-ref" class="ltr"></div><button type="button" class="btn primary" data-act="confirm-card">ثبت پرداخت کارت</button>`;
  if (modal.type === "gateway") inner = `<h2 class="section-title">پرداخت در مرورگر</h2><p>فاکتور ${num(modal.sale.id)} · ${money(modal.sale.payable)}</p><p class="hint">صفحه زیبال در مرورگر باز شده است. آی‌پی این رایانه برای درگاه لازم نیست.</p>${modal.sale.pay_url ? `<p><a href="${esc(modal.sale.pay_url)}" target="_blank" rel="noopener">اگر صفحه باز نشد، اینجا را بزنید</a></p>` : ""}<div class="row-actions"><button type="button" class="btn primary" data-act="verify-sale" data-id="${modal.sale.id}">استعلام تأیید</button><button type="button" class="btn danger" data-act="cancel-sale" data-id="${modal.sale.id}">لغو</button></div><form data-act="manual-gateway"><input type="hidden" name="id" value="${modal.sale.id}"><div class="field"><label>اگر در پنل درگاه پرداخت را دیدید، پیگیری را بنویسید</label><input name="ref" required></div><button class="btn" type="submit">ثبت دستی</button></form>`;
  if (modal.type === "license") {
    const lic = modal.license;
    inner = `<h2 class="section-title">پرداخت لایسنس در زیبال</h2><p>${esc(lic.title)} · ${esc(lic.buyer_name)} · ${money(lic.payable)}</p>${lic.pay_url ? `<p><a href="${esc(lic.pay_url)}" target="_blank" rel="noopener">باز کردن صفحه زیبال</a></p>` : ""}<div class="row-actions"><button type="button" class="btn primary" data-act="verify-license" data-id="${lic.id}">استعلام تأیید</button><button type="button" class="btn danger" data-act="cancel-license" data-id="${lic.id}">لغو</button></div><form data-act="manual-license"><input type="hidden" name="id" value="${lic.id}"><div class="field"><label>اگر در پنل زیبال پرداخت را دیدید، پیگیری را بنویسید</label><input name="ref" required></div><button class="btn" type="submit">ثبت دستی</button></form>`;
  }
  if (modal.type === "receipt") inner = receiptHtml(modal);
  if (modal.type === "import") {
    const preview = modal.preview;
    const rows = preview?.preview || [];
    const table = rows.length ? `<table><thead><tr><th>نام کالا</th><th>SKU</th><th>موجودی</th><th>قیمت فروش</th></tr></thead><tbody>
      ${rows.map((item) => `<tr><td>${esc(item.name)}</td><td class="ltr">${esc(item.sku || "—")}</td><td class="num">${num(item.stock)}</td><td class="num">${num(item.price)}</td></tr>`).join("")}
    </tbody></table>` : "";
    const problems = preview?.error_count ? `<p class="hint">${num(preview.error_count)} ردیف رد می‌شود. ${preview.errors.slice(0, 3).map((row) => `ردیف ${num(row.row)}: ${esc(row.error)}`).join(" · ")}</p>` : "";
    inner = `<h2 class="section-title">ورود محصولات با فایل اکسل</h2>
      <div class="row-actions">
        <label class="btn">انتخاب فایل<input id="excel-file" type="file" accept=".xlsx,.xlsm" hidden></label>
        <a class="btn" href="/api/products/template">دانلود قالب نمونه اکسل</a>
      </div>
      <p class="hint">${modal.name ? esc(modal.name) : "ستون‌ها را مثل قالب بگذارید: نام کالا، SKU، موجودی، قیمت فروش. قیمت صفر هم ذخیره می‌شود."}</p>
      ${preview ? `<p>پیش‌نمایش ${num(rows.length)} ردیف از ${num(preview.total)} کالا. ${num(preview.updating || 0)} کالا با نام یا کد قبلی به‌روز می‌شود و ${num(preview.creating || 0)} کالا تازه است.</p>${table}${problems}` : ""}
      <div class="row-actions">
        <button type="button" class="btn primary" data-act="commit-import" ${preview?.total ? "" : "disabled"}>ثبت ${num(preview?.total || 0)} کالا</button>
        <button type="button" class="btn" data-act="close-modal">انصراف</button>
      </div>`;
  }
  if (modal.type === "password") inner = `<form data-act="change-password"><h2 class="section-title">تغییر رمز</h2><div class="field"><label>رمز فعلی</label><input type="password" name="current" required></div><div class="field"><label>رمز جدید</label><input type="password" name="password" minlength="6" required></div><button class="btn primary" type="submit">ذخیره</button></form>
    <form data-act="attach-email"><h2 class="section-title">ورود با جیمیل</h2><p class="hint">همین جیمیل را ذخیره کنید و بعد با آن وارد شوید.</p><div class="field"><label>جیمیل</label><input class="ltr" name="email" type="email" value="${esc(state.user.email || "")}" required placeholder="name@gmail.com"></div><button class="btn primary" type="submit">ذخیره جیمیل</button></form>
    <form data-act="verify-email"><div class="field"><label>کد ۶ رقمی جیمیل</label><input class="ltr" name="code" inputmode="numeric" required></div><button class="btn" type="submit">تأیید جیمیل</button></form>`;
  const wide = modal.type === "receipt" ? "invoice-modal" : (modal.type === "import" ? "import-modal" : "");
  return `<div class="modal-back" data-act="close-modal"><div class="modal card ${wide}" data-act="stop"><div class="row-actions"><button type="button" class="btn" data-act="close-modal">بستن</button></div>${inner}</div></div>`;
}

function pageHtml() {
  if (state.access && !state.access.active && state.page !== "licenses" && state.page !== "settings") {
    return `<section class="card access-card"><h2>مهلت ۷ روز رایگان تمام شده</h2><p class="hint">فروش تا خرید لایسنس بسته است. اطلاعات فروشگاه سر جایش می‌ماند.</p><button type="button" class="btn primary" data-act="nav" data-page="licenses">خرید لایسنس</button></section>`;
  }
  const pages = {
    dashboard: dashboardHtml, pos: posHtml, products: productsHtml, inventory: inventoryHtml,
    accounts: accountsHtml, register: registerHtml, licenses: licensesHtml, customers: customersHtml,
    sms: smsHtml, settings: settingsHtml,
  };
  const draw = pages[state.page];
  return draw ? draw() : "";
}
function render() {
  if (!state.user) {
    $app().innerHTML = authHtml();
    return;
  }
  const shell = document.querySelector(".webapp");
  if (!shell || shell.dataset.user !== String(state.user.id)) $app().innerHTML = webShell();
  const view = document.getElementById("view");
  if (view) view.innerHTML = pageHtml();
  paintChrome();
  if (state.focusBarcode) {
    document.getElementById("barcode")?.focus();
    state.focusBarcode = false;
  }
}

function closePopup(popup) {
  try { if (popup && !popup.closed) popup.close(); } catch { /* پنجره را مرورگر بسته است */ }
}

function watchLicense(id) {
  let tries = 0;
  const timer = setInterval(() => {
    tries += 1;
    if (tries > 40 || state.modal?.license?.id !== id) {
      clearInterval(timer);
      return;
    }
    api(`/api/licenses/${id}/confirm`, { method: "POST", body: { mode: "verify" } }).then(async (result) => {
      clearInterval(timer);
      state.modal = null;
      toast(`لایسنس فعال شد: ${money(result.payable)}`);
      await loaders.licenses();
      state.access = state.licenses?.access || state.access;
      render();
    }).catch((err) => {
      if (err.status === 409) return;
      clearInterval(timer);
    });
  }, 4000);
}

async function buyLicense(plan, _preset, popup) {
  state.plan = plan;
  const data = {
    plan,
    payment_method: "gateway",
    buyer_name: state.user?.name || "خریدار",
    phone: state.user?.phone || "",
    discount_value: "0",
    discount_type: "amount",
  };
  try {
    const result = await api("/api/licenses", { method: "POST", body: data });
    const url = result.license?.pay_url || "";
    if (!url) {
      closePopup(popup);
      throw new Error("زیبال صفحه پرداخت نداد");
    }
    if (popup && !popup.closed) popup.location.href = url;
    else location.assign(url);
    state.modal = { type: "license", license: result.license };
    await loaders.licenses();
    state.access = state.licenses?.access || state.access;
    render();
    watchLicense(result.license.id);
  } catch (err) {
    closePopup(popup);
    throw err;
  }
}

async function onSubmit(event) {
  const form = event.target.closest("form[data-act]");
  if (!form) return;
  event.preventDefault();
  const act = form.dataset.act;
  const data = Object.fromEntries(new FormData(form).entries());
  if (!state.user) state.authDraft = data;
  const licensePopup = act === "sell-license" && !state.busy ? window.open("about:blank", "_blank") : null;
  await guard(async () => {
    if (act === "login") {
      try {
        const result = await api("/api/auth/login", { method: "POST", body: data });
        state.user = result.user;
        state.mustChange = result.must_change_password;
        state.access = result.access || null;
        state.shop = result.shop || null;
        hideToast();
        await navigate("dashboard");
      } catch (err) {
        if (err.data?.needs_verify) {
          state.pendingEmail = err.data.ident || data.ident;
          state.verifyNote = err.message;
          state.authView = "verify";
          render();
          return;
        }
        throw err;
      }
    } else if (act === "register") {
      const result = await api("/api/auth/register", { method: "POST", body: data });
      state.authError = "";
      if (result.needs_verify) {
        state.pendingEmail = result.email;
        state.verifyNote = "کد شش‌رقمی به جیمیل فرستاده شد. صندوق ورودی و هرزنامه را ببینید.";
        state.authView = "verify";
        render();
      } else {
        state.user = result.user;
        state.mustChange = result.must_change_password;
        hideToast();
        await navigate("dashboard");
      }
    } else if (act === "send-support") {
      const result = await api("/api/support/messages", { method: "POST", body: {
        kind: data.kind === "bug" ? "bug" : "chat",
        body: data.body,
        page: state.page,
        error: state.lastError || "",
      } });
      state.supportLog = (await api("/api/support/messages")).messages;
      state.support = true;
      toast(result.detail || "پیام ثبت شد");
      paintChrome();
    } else if (act === "verify") {
      await api("/api/auth/verify", { method: "POST", body: { ident: data.ident, code: data.code } });
      state.authView = "login";
      toast("جیمیل تأیید شد. حالا وارد شوید.");
      render();
    } else if (act === "attach-email") {
      const result = await api("/api/auth/email", { method: "POST", body: { email: data.email } });
      state.user.email = result.email;
      state.user.email_verified = result.needs_verify ? 0 : 1;
      toast(result.needs_verify ? "کد به جیمیل فرستاده شد" : "جیمیل ذخیره شد");
      render();
    } else if (act === "verify-email") {
      await api("/api/auth/verify", { method: "POST", body: { ident: state.user.email, code: data.code } });
      state.user = (await api("/api/auth/me")).user;
      state.modal = null;
      toast("جیمیل تأیید شد. از این به بعد با همین جیمیل هم می‌توانید وارد شوید.");
      render();
    } else if (act === "forgot") {
      const result = await api("/api/auth/forgot", { method: "POST", body: { ident: data.ident } });
      state.recovery = { ident: data.ident, code: result.preview_code || "", delivery: result.delivery, detail: result.detail };
      state.authView = "reset";
      render();
    } else if (act === "reset") {
      await api("/api/auth/reset", { method: "POST", body: data });
      state.authView = "login";
      toast("رمز عوض شد. وارد شوید.");
      render();
    } else if (act === "save-product") await saveProduct(form, data);
    else if (act === "save-settings") await saveSettings(form);
    else if (act === "create-user") {
      await api("/api/users", { method: "POST", body: data });
      await loaders.settings();
      toast("کاربر ساخته شد");
      render();
    } else if (act === "change-password") {
      await api("/api/auth/password", { method: "POST", body: data });
      state.mustChange = false;
      state.modal = null;
      toast("رمز عوض شد");
      render();
    } else if (act === "adjust") {
      await api("/api/inventory/adjust", { method: "POST", body: data });
      await loaders.inventory();
      render();
    } else if (act === "purchase") {
      await api("/api/purchases", { method: "POST", body: data });
      await loaders.inventory();
      toast("خرید ثبت شد");
      render();
    } else if (act === "journal") await saveJournal(data);
    else if (act === "create-account") {
      await api("/api/accounts", { method: "POST", body: data });
      await loaders.accounts();
      render();
    } else if (act === "open-register") {
      await api("/api/register/open", { method: "POST", body: data });
      await loaders.register();
      render();
    } else if (act === "close-register") {
      const result = await api("/api/register/close", { method: "POST", body: data });
      toast(`صندوق بسته شد. اختلاف ${money(result.difference)}`);
      await loaders.register();
      render();
    } else if (act === "sell-license") {
      await buyLicense(state.plan, data, licensePopup);
    } else if (act === "save-prices") {
      await api("/api/licenses/prices", { method: "PUT", body: data });
      await loaders.licenses();
      toast("قیمت‌ها ذخیره شد");
      render();
    } else if (act === "receipt") {
      await api("/api/receipts", { method: "POST", body: data });
      await loaders.customers();
      toast("طلب دریافت شد");
      render();
    } else if (act === "send-sms") {
      const result = await api("/api/sms", { method: "POST", body: data });
      toast(result.status === "sent" ? "پیامک ارسال شد" : result.detail || "در سیستم ثبت شد");
      await loaders.sms();
      render();
    } else if (act === "manual-gateway") {
      await api(`/api/sales/${data.id}/confirm`, { method: "POST", body: { mode: "manual", ref: data.ref } });
      state.modal = null;
      state.cart = [];
      await loaders.pos();
      toast("پرداخت ثبت شد");
      render();
    } else if (act === "manual-license") {
      const result = await api(`/api/licenses/${data.id}/confirm`, { method: "POST", body: { mode: "manual", ref: data.ref } });
      state.modal = null;
      toast(`لایسنس ثبت شد: ${money(result.payable)}`);
      await loaders.licenses();
      render();
    }
  });
}

async function saveProduct(form, data) {
  const file = form.querySelector('input[type="file"]')?.files?.[0];
  if (file) {
    const body = new FormData();
    body.append("file", file);
    const uploaded = await api("/api/upload", { method: "POST", form: body });
    data.image = uploaded.url;
  }
  delete data.file;
  const id = data.id;
  delete data.id;
  if (id) await api(`/api/products/${id}`, { method: "PATCH", body: data });
  else await api("/api/products", { method: "POST", body: data });
  state.modal = null;
  await loaders.products();
  toast("کالا ذخیره شد");
  render();
}
async function saveSettings(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const file = form.querySelector('input[name="logo_file"]')?.files?.[0];
  if (file) {
    const body = new FormData();
    body.append("file", file);
    const uploaded = await api("/api/upload", { method: "POST", form: body });
    data.shop_logo = uploaded.url;
  }
  if (form.querySelector('[name="clear_shop_logo"]')?.checked) data.shop_logo = "";
  delete data.logo_file;
  delete data.clear_shop_logo;
  for (const key of ["gateway_sandbox", "sms_on_close", "sms_on_sale", "sms_low_stock", "moadian_enabled", "moadian_sandbox"]) {
    data[key] = form.querySelector(`[name="${key}"]`)?.checked ? "1" : "0";
  }
  state.settings = (await api("/api/settings", { method: "PUT", body: data })).settings;
  state.shop = { name: state.settings.shop_name || "دفترچی", logo: state.settings.shop_logo || "" };
  toast("تنظیمات ذخیره شد");
  render();
}
async function saveJournal(data) {
  const amount = asInt(data.amount);
  if (!amount) return toast("مبلغ را وارد کنید");
  if (data.account_id === data.counter_id) return toast("دو حساب باید متفاوت باشند");
  const first = Number(data.account_id);
  const second = Number(data.counter_id);
  const lines = data.side === "credit"
    ? [{ account_id: first, debit: 0, credit: amount }, { account_id: second, debit: amount, credit: 0 }]
    : [{ account_id: first, debit: amount, credit: 0 }, { account_id: second, debit: 0, credit: amount }];
  await api("/api/journal", { method: "POST", body: { memo: data.memo, lines } });
  await loaders.accounts();
  toast("سند ثبت شد");
  render();
}
function buyerReady() {
  syncPos();
  const first = state.buyerFirst.trim();
  const last = state.buyerLast.trim();
  const phone = String(state.buyerPhone || "")
    .replace(/[۰-۹]/g, (digit) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String("٠١٢٣٤٥٦٧٨٩".indexOf(digit)))
    .replace(/\D/g, "");
  if (first.length < 2 || last.length < 2) {
    toast("نام و نام خانوادگی خریدار را بنویسید");
    return null;
  }
  if (!/^09\d{9}$/.test(phone)) {
    toast("شماره موبایل خریدار را وارد کنید");
    return null;
  }
  return { first, last, phone };
}
async function submitSale(method, posRef, popup) {
  const buyer = buyerReady();
  if (!buyer || !state.cart.length) {
    closePopup(popup);
    if (!buyer) return;
    return toast("سبد خالی است");
  }
  let result;
  try {
    result = await api("/api/sales", {
    method: "POST",
    body: {
      items: state.cart.map((line) => ({ product_id: line.id, variation_id: line.variationId || 0, qty: line.qty })),
      discount_type: state.discountType,
      discount_value: state.discountType === "percent" ? Math.round(asInt(state.discountValue)) : asInt(state.discountValue),
      payment_method: method,
      customer_first: buyer.first,
      customer_last: buyer.last,
      customer_phone: buyer.phone,
      pos_ref: posRef || "",
    },
  });
  } catch (err) {
    closePopup(popup);
    throw err;
  }
  hideToast();
  if (result.sale.status === "pending") {
    const url = result.sale.pay_url || "";
    if (url && popup && !popup.closed) popup.location.href = url;
    else if (url) window.open(url, "_blank", "noopener");
    state.modal = { type: "gateway", sale: result.sale };
  } else {
    closePopup(popup);
    state.cart = [];
    state.discountValue = "";
    state.buyerFirst = "";
    state.buyerLast = "";
    state.buyerPhone = "";
    state.modal = { type: "receipt", sale: result.sale, items: result.items, sms: result.sms };
  }
  await loaders.pos();
  render();
}

async function onClick(event) {
  const el = event.target.closest("[data-act]");
  if (!el || el.tagName === "FORM") return;
  if (el.closest("form[data-act]") && el.type === "submit") return;
  if (el.dataset.act === "stop") { event.stopPropagation(); return; }
  const act = el.dataset.act;
  if (act === "close-modal") { state.modal = null; render(); return; }
  if (act === "show-forgot") { state.authView = "forgot"; state.authError = ""; render(); return; }
  if (act === "show-register") { state.authView = "register"; state.authError = ""; render(); return; }
  if (act === "show-login") { state.authView = "login"; state.authError = ""; render(); return; }
  if (act === "resend-verify") {
    await guard(async () => {
      await api("/api/auth/verify/resend", { method: "POST", body: { ident: state.pendingEmail || document.querySelector('[name="ident"]')?.value || "" } });
      state.verifyNote = "کد تازه به جیمیل فرستاده شد.";
      toast("کد دوباره فرستاده شد");
      render();
    });
    return;
  }
  if (act === "nav") { await guard(() => navigate(el.dataset.page)); return; }
  if (act === "chart") { state.chart = el.dataset.range; render(); return; }
  if (act === "pick-plan") {
    const popup = window.open("about:blank", "_blank");
    await guard(() => buyLicense(el.dataset.plan, null, popup));
    return;
  }
  if (act === "print") { window.print(); return; }
  if (act === "password-modal") { state.modal = { type: "password" }; render(); return; }
  if (act === "toggle-support" || act === "report-error" || act === "support-tab") {
    if (act === "toggle-support" && state.support && !el.dataset.tab) {
      state.support = false;
      paintChrome();
      return;
    }
    await guard(async () => {
      state.support = true;
      if (act === "report-error") state.supportTab = "bug";
      if (el.dataset.tab) state.supportTab = el.dataset.tab;
      state.supportLog = (await api("/api/support/messages")).messages;
      paintChrome();
    });
    return;
  }
  if (act === "pay" && el.dataset.method === "gateway") {
    if (!buyerReady()) return;
    const popup = window.open("about:blank", "_blank");
    await guard(() => submitSale("gateway", "", popup));
    return;
  }
  if (act === "open-import") { state.modal = { type: "import", name: "", preview: null }; render(); return; }
  if (act === "more-products" || act === "more-pos" || act === "more-inventory") {
    if (act === "more-products") state.productLimit += PAGE_SIZE;
    if (act === "more-pos") state.posLimit += PAGE_SIZE;
    if (act === "more-inventory") state.inventoryLimit += PAGE_SIZE;
    const box = document.getElementById(act === "more-pos" ? "pos-grid" : act === "more-inventory" ? "inventory-box" : "product-table");
    if (box) box.innerHTML = act === "more-pos" ? posTiles() : act === "more-inventory" ? inventoryTable() : productRows();
    return;
  }
  await guard(async () => {
    if (act === "logout") {
      await api("/api/auth/logout", { method: "POST" });
      state.user = null;
      state.cart = [];
      state.bootstrap = await api("/api/auth/bootstrap");
      state.authView = "login";
      history.replaceState(null, "", location.pathname);
      render();
    } else if (act === "add-cart") {
      syncPos();
      addProduct(state.products.find((item) => item.id === Number(el.dataset.id)));
    } else if (act === "pick-variation") {
      const product = state.products.find((item) => item.id === Number(el.dataset.id)) || state.modal?.product;
      addProduct(product, variationOf(product, el.dataset.variation));
    } else if (act === "inc" || act === "dec" || act === "remove-line") {
      syncPos();
      const line = state.cart.find((item) => item.id === Number(el.dataset.id) && (item.variationId || 0) === Number(el.dataset.variation || 0));
      if (!line) return;
      if (act === "remove-line") state.cart = state.cart.filter((item) => item !== line);
      else       if (act === "inc") {
        if (line.tracked !== false && line.qty + 1 > line.stock) return toast("موجودی کافی نیست");
        line.qty += 1;
      } else line.qty -= 1;
      if (line.qty <= 0) state.cart = state.cart.filter((item) => item !== line);
      render();
    } else if (act === "pay") {
      if (!buyerReady()) return;
      if (el.dataset.method === "card") {
        const prep = await api("/api/pos/prepare", { method: "POST", body: { amount: cartSubtotal() - cartDiscount() } });
        state.modal = { type: "card", message: prep.message, ok: prep.ok };
        render();
      } else await submitSale(el.dataset.method, "");
    } else if (act === "confirm-card") {
      await submitSale("card", document.getElementById("pos-ref")?.value || "");
    } else if (act === "check-update") {
      await loadUpdate();
      state.support = true;
      state.supportTab = "update";
      toast(state.update?.update ? `نسخه ${state.update.version} آماده است` : "نسخه تازه‌ای نیست");
      paintChrome();
    } else if (act === "commit-import") {
      if (!state.importFile || !state.modal?.preview?.total) return toast("اول فایل اکسل را انتخاب کنید");
      const body = new FormData();
      body.append("file", state.importFile);
      const result = await api("/api/products/import", { method: "POST", form: body });
      state.importResult = result;
      state.importFile = null;
      state.modal = null;
      await loaders.products();
      const saved = (result.created || 0) + (result.updated || 0);
      toast(result.errors?.length ? `${num(saved)} کالا ثبت شد و ${num(result.errors.length)} ردیف رد شد` : `${num(saved)} کالا ثبت شد`);
      render();
    } else if (act === "new-product") { state.modal = { type: "product", product: null }; render(); }
    else if (act === "edit-product") {
      state.modal = { type: "product", product: state.products.find((item) => item.id === Number(el.dataset.id)) };
      render();
    } else if (act === "archive-product") {
      if (!window.confirm("این کالا بایگانی شود؟")) return;
      await api(`/api/products/${el.dataset.id}`, { method: "DELETE" });
      await loaders.products();
      render();
    } else if (act === "woo-push" || act === "woo-push-ids") {
      const body = act === "woo-push-ids" ? { ids: state.importResult?.ids || [] } : {};
      const result = await api("/api/products/woo/push", { method: "POST", body });
      const skipped = result.skipped ? `، ${num(result.skipped)} متغیر دست نخورد` : "";
      const failed = result.failed?.length ? `، ${num(result.failed.length)} تا نماند. قبلی‌ها ذخیره شد` : "";
      toast(`ووکامرس: ${num(result.created)} جدید، ${num(result.updated)} به‌روز${skipped}${failed}`, { error: Boolean(result.failed?.length) });
      await loaders.products();
      render();
    } else if (act === "woo-pull") {
      const result = await api("/api/products/woo/pull", { method: "POST", body: {} });
      toast(`از ووکامرس ${num(result.imported)} کالا آمد و ${num(result.updated)} به‌روز شد`);
      await loaders.products();
      render();
    } else if (act === "verify-sale" || act === "open-gateway") {
      const id = el.dataset.id;
      if (act === "verify-sale") {
        const result = await api(`/api/sales/${id}/confirm`, { method: "POST", body: { mode: "verify" } });
        state.modal = { type: "receipt", sale: result.sale, items: result.items, sms: result.sms };
        state.cart = [];
      } else {
        const sale = state.pending.find((item) => item.id === Number(id));
        state.modal = { type: "gateway", sale };
      }
      await loaders.pos();
      render();
    } else if (act === "cancel-sale") {
      await api(`/api/sales/${el.dataset.id}/cancel`, { method: "POST", body: {} });
      state.modal = null;
      await loaders.pos();
      render();
    } else if (act === "verify-license" || act === "open-license") {
      const id = el.dataset.id;
      if (act === "verify-license") {
        const result = await api(`/api/licenses/${id}/confirm`, { method: "POST", body: { mode: "verify" } });
        state.modal = null;
        toast(`لایسنس پرداخت شد: ${money(result.payable)}`);
      } else {
        const license = state.licenses?.licenses?.find((item) => item.id === Number(id));
        if (license) state.modal = { type: "license", license };
      }
      await loaders.licenses();
      render();
    } else if (act === "cancel-license") {
      await api(`/api/licenses/${el.dataset.id}/cancel`, { method: "POST", body: {} });
      state.modal = null;
      await loaders.licenses();
      render();
    } else if (act === "filter-account") {
      state.accountId = el.dataset.id || "";
      await loaders.accounts();
      render();
    } else if (act === "moadian-send" || act === "moadian-inquiry") {
      const path = act === "moadian-send" ? "moadian" : "moadian/inquiry";
      const result = await api(`/api/sales/${el.dataset.id}/${path}`, { method: "POST", body: {} });
      if (state.modal?.type === "receipt") {
        state.modal.sale = result.sale;
        state.modal.items = result.items;
      }
      toast(result.message || "انجام شد");
      render();
    } else if (act === "test-setting") {
      const form = document.querySelector("form[data-act=save-settings]");
      const data = form ? Object.fromEntries(new FormData(form).entries()) : {};
      if (el.dataset.kind === "woo" && !String(data.woo_key || "").trim()) {
        toast("کادر Consumer key خالی است. کلید را بچسبانید؛ با ck_ شروع می‌شود.");
        return;
      }
      const result = await api(`/api/settings/test/${el.dataset.kind}`, { method: "POST", body: {
        wp_url: data.wp_url || "",
        woo_key: data.woo_key || "",
        woo_secret: data.woo_secret || "",
      } });
      toast(result.message);
    }
  });
}

function refreshPayable() {
  syncPos();
  const subtotal = cartSubtotal();
  const discount = cartDiscount();
  const set = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };
  set("pay-sub", money(subtotal));
  set("pay-disc", money(discount));
  set("pay-due", money(subtotal - discount));
}
function onInput(event) {
  if (event.target.id === "discount") refreshPayable();
  if (event.target.id === "pos-query") {
    state.posQuery = event.target.value;
    state.posLimit = PAGE_SIZE;
    const box = document.getElementById("pos-grid");
    if (box) box.innerHTML = posTiles();
  }
  if (event.target.id === "product-query") {
    state.productQuery = event.target.value;
    state.productLimit = PAGE_SIZE;
    const box = document.getElementById("product-table");
    if (box) box.innerHTML = productRows();
  }
  if (event.target.id === "inventory-query") {
    state.inventoryQuery = event.target.value;
    state.inventoryLimit = PAGE_SIZE;
    const box = document.getElementById("inventory-box");
    if (box) box.innerHTML = inventoryTable();
    document.querySelectorAll("form[data-act=adjust] select[name=product_id], form[data-act=purchase] select[name=product_id]").forEach((select) => {
      select.innerHTML = stockChoices(inventoryFiltered().slice(0, PAGE_SIZE));
    });
  }
}
function onChange(event) {
  if (event.target.id === "discount-type") refreshPayable();
  if (event.target.id === "excel-file" && event.target.files[0]) {
    const file = event.target.files[0];
    state.importFile = file;
    guard(async () => {
      const body = new FormData();
      body.append("file", file);
      const preview = await api("/api/products/preview", { method: "POST", form: body });
      state.modal = { type: "import", name: file.name, preview };
      render();
    });
  }
}

let scanBuffer = "";
let scanAt = 0;
document.addEventListener("keydown", (event) => {
  if (!state.user || state.page !== "pos" || state.modal) return;
  const inField = event.target.matches("input, textarea, select");
  if (inField && event.target.dataset.barcode !== "1") return;
  const now = Date.now();
  if (now - scanAt > 80) scanBuffer = "";
  scanAt = now;
  if (event.key === "Enter") {
    const code = event.target.dataset?.barcode === "1" ? event.target.value : scanBuffer;
    scanBuffer = "";
    if (code && code.trim().length >= 3) {
      event.preventDefault();
      guard(() => addByBarcode(code));
    }
  } else if (!inField && event.key.length === 1) scanBuffer += event.key;
});
document.addEventListener("submit", onSubmit);
document.addEventListener("click", onClick);
document.addEventListener("input", onInput);
document.addEventListener("change", onChange);
window.addEventListener("error", (event) => {
  if (!event.message || event.message === "Script error.") return;
  toast(event.message, { error: true });
});
window.addEventListener("unhandledrejection", (event) => {
  const message = event.reason && event.reason.message ? event.reason.message : "";
  if (message) toast(message, { error: true });
});
window.addEventListener("hashchange", () => {
  const page = location.hash.replace("#", "");
  if (state.user && page && page !== state.page) guard(() => navigate(page));
});

api("/api/auth/me").then(async (me) => {
  loadUpdate().then(() => {
    if (!state.user) render();
  });
  if (!me.user) {
    state.bootstrap = await api("/api/auth/bootstrap");
    render();
    return;
  }
  state.user = me.user;
  state.mustChange = me.must_change_password;
  state.access = me.access || null;
  state.shop = me.shop || null;
  await navigate(location.hash.replace("#", "") || "dashboard");
}).catch((err) => {
  $app().innerHTML = `<p class="empty">${esc(err.message || "برنامه باز نشد")}</p>`;
});
