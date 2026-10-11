const NAV = [
  ["dashboard", "پیشخوان"],
  ["pos", "فروش"],
  ["products", "محصولات", "admin"],
  ["inventory", "انبار", "admin"],
  ["accounts", "حسابداری", "admin"],
  ["register", "صندوق"],
  ["licenses", "لایسنس", "admin"],
  ["customers", "مشتریان"],
  ["sms", "پیامک", "admin"],
  ["settings", "تنظیمات", "admin"],
];
const TITLES = Object.fromEntries(NAV.map(([id, title]) => [id, title]));
const PAY = { cash: "نقد", card: "کارت", gateway: "درگاه", credit: "نسیه" };
const TYPES = { asset: "دارایی", liability: "بدهی", equity: "سرمایه", income: "درآمد", expense: "هزینه", person: "شخص" };
const KINDS = { sale: "فروش", purchase: "خرید", adjust: "تعدیل", price: "تغییر قیمت" };

const state = {
  user: null,
  mustChange: false,
  bootstrap: null,
  authView: "login",
  recovery: null,
  page: "dashboard",
  busy: false,
  modal: null,
  chart: "week",
  focusBarcode: false,
  products: [],
  productQuery: "",
  cart: [],
  discountType: "amount",
  discountValue: "",
  buyerName: "",
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
  plan: "12m",
  sms: [],
  settings: null,
  users: [],
  importResult: null,
};

const $app = () => document.getElementById("app");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}
function money(value) {
  return `${new Intl.NumberFormat("fa-IR").format(Math.round(Number(value) || 0))} تومان`;
}
function num(value) {
  return new Intl.NumberFormat("fa-IR").format(Number(value) || 0);
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
  return `<img class="${small ? "thumb sm" : ""}" src="${esc(safe)}" alt="${esc(alt || "")}">`;
}
function toast(message) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 3600);
}
async function api(path, { method = "GET", body, form } = {}) {
  const opts = { method, credentials: "same-origin" };
  if (form) opts.body = form;
  else if (body !== undefined) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    state.user = null;
    render();
    throw new Error(data.error || "وارد نشده‌اید");
  }
  if (!res.ok) throw new Error(data.error || "خطا");
  return data;
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
  catch (err) { toast(err.message || "خطا"); }
  finally { state.busy = false; }
}

const loaders = {
  async dashboard() {
    const [summary, sales, registerInfo] = await Promise.all([
      api("/api/reports/summary"), api("/api/sales?limit=8"), api("/api/register"),
    ]);
    state.dashboard = summary;
    state.sales = sales.sales;
    state.registerInfo = registerInfo;
  },
  async pos() {
    const [products, pending, registerInfo] = await Promise.all([
      api("/api/products"), api("/api/sales?status=pending&limit=20"), api("/api/register"),
    ]);
    state.products = products.products;
    state.pending = pending.sales;
    state.registerInfo = registerInfo;
    syncCartStock();
  },
  async products() {
    state.products = (await api("/api/products")).products;
  },
  async inventory() {
    state.inventory = await api("/api/inventory");
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
  },
  async customers() {
    state.customers = (await api("/api/customers")).customers;
  },
  async sms() {
    state.sms = (await api("/api/sms")).messages;
  },
  async settings() {
    const [settings, users] = await Promise.all([api("/api/settings"), api("/api/users")]);
    state.settings = settings.settings;
    state.users = users.users;
  },
};

async function navigate(page) {
  if (!allowed(page)) page = "dashboard";
  state.page = page;
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
  read("buyer-name", "buyerName");
  read("buyer-phone", "buyerPhone");
  read("pos-query", "posQuery");
}
function syncCartStock() {
  state.cart = state.cart.map((line) => {
    const product = state.products.find((item) => item.id === line.id);
    if (!product || product.stock <= 0) return null;
    return { ...line, name: product.name, price: product.price, stock: product.stock, qty: Math.min(line.qty, product.stock) };
  }).filter(Boolean);
}
function addProduct(product) {
  if (!product || product.stock <= 0) return toast("این کالا موجودی ندارد");
  const line = state.cart.find((item) => item.id === product.id);
  if ((line?.qty || 0) + 1 > product.stock) return toast("موجودی کافی نیست");
  if (line) line.qty += 1;
  else state.cart.push({ id: product.id, name: product.name, price: product.price, qty: 1, stock: product.stock, image: product.image });
  state.focusBarcode = true;
  render();
}
async function addByBarcode(code) {
  const trimmed = code.trim();
  if (trimmed.length < 3) return;
  let product = state.products.find((item) => item.barcode === trimmed);
  if (!product) {
    const data = await api(`/api/products?q=${encodeURIComponent(trimmed)}`);
    product = data.products.find((item) => item.barcode === trimmed);
  }
  if (!product) return toast("کالایی با این بارکد نیست");
  addProduct(product);
  const input = document.getElementById("barcode");
  if (input) input.value = "";
}

function authHtml() {
  if (state.authView === "reset") {
    const recovery = state.recovery || {};
    return `<div class="auth"><form class="card auth-card" data-act="reset">
      <div class="brand"><div class="mark">${logo()}</div><div><strong>بازیابی رمز</strong><span>دفترچی</span></div></div>
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
      <div class="field"><label>موبایل یا جیمیل</label><input name="ident" required></div>
      <button class="btn primary block" type="submit">دریافت کد</button>
      <button class="btn block" type="button" data-act="show-login">بازگشت</button>
    </form></div>`;
  }
  const initial = state.bootstrap?.initial
    ? `<p class="hint">ورود اولیه: <span class="ltr">${esc(state.bootstrap.phone)}</span> / ${esc(state.bootstrap.password)}</p>`
    : "";
  return `<div class="auth"><form class="card auth-card" data-act="login">
    <div class="brand"><div class="mark">${logo()}</div><div><strong>دفترچی</strong><span>صندوق و حسابداری فروشگاه</span></div></div>
    <div class="field"><label>موبایل یا جیمیل</label><input name="ident" autocomplete="username" required value="${state.bootstrap?.initial ? esc(state.bootstrap.phone) : ""}"></div>
    <div class="field"><label>رمز</label><input type="password" name="password" autocomplete="current-password" required></div>
    <button class="btn primary block" type="submit">ورود</button>
    <button class="btn block" type="button" data-act="show-forgot">رمز را فراموش کرده‌ام</button>
    ${initial}
  </form></div>`;
}
function logo() {
  return `<svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true"><rect x="6" y="4" width="20" height="24" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4v24M16 12h6M16 17h6" stroke="currentColor" stroke-width="2"/></svg>`;
}
function shell(content) {
  const nav = NAV.filter((item) => item[2] !== "admin" || isAdmin()).map(([id, title]) => (
    `<button type="button" class="nav-btn ${state.page === id ? "active" : ""}" data-act="nav" data-page="${id}">${title}</button>`
  )).join("");
  const open = state.registerInfo?.open;
  const pill = state.registerInfo
    ? `<span class="pill ${open ? "" : "warn"}">${open ? "صندوق باز" : "صندوق بسته"}</span>`
    : "";
  const banner = state.mustChange
    ? `<div class="banner">رمز اولیه هنوز فعال است. <button type="button" class="btn" data-act="password-modal">عوضش کنید</button></div>`
    : "";
  return `<div class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="mark">${logo()}</div><div><strong>دفترچی</strong><span>${esc(state.user.name)}</span></div></div>
      <nav>${nav}</nav>
      <div class="side-foot">${esc(state.user.role === "admin" ? "مدیر" : "صندوقدار")}</div>
    </aside>
    <main class="main">
      <header class="topbar">
        <div><h1>${TITLES[state.page] || ""}</h1></div>
        <div class="top-actions">${pill}<button type="button" class="btn" data-act="password-modal">تغییر رمز</button><button type="button" class="btn" data-act="logout">خروج</button></div>
      </header>
      ${banner}${content}
    </main>
  </div>`;
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

function posTiles() {
  const query = state.posQuery.trim();
  const rows = state.products.filter((product) => !query || `${product.name} ${product.barcode} ${product.sku}`.includes(query));
  if (!rows.length) return `<p class="empty">کالایی پیدا نشد.</p>`;
  return `<div class="product-grid">${rows.map((product) => `<button type="button" class="tile" data-act="add-cart" data-id="${product.id}" ${product.stock <= 0 ? "disabled" : ""}>
    ${thumb(product.image, product.name)}
    <span class="pname">${esc(product.name)}</span>
    <span class="num">${money(product.price)}</span>
    <span class="pstock">موجودی ${num(product.stock)}${product.low ? " · کم" : ""}</span>
  </button>`).join("")}</div>`;
}
function posHtml() {
  const subtotal = cartSubtotal();
  const discount = cartDiscount();
  const payable = subtotal - discount;
  const closed = state.registerInfo && !state.registerInfo.open;
  const lines = state.cart.length ? state.cart.map((line) => `<div class="line"><div><strong>${esc(line.name)}</strong><div class="muted num">${money(line.price)}</div></div>
    <div><div class="qty"><button type="button" data-act="dec" data-id="${line.id}">−</button><span class="num">${num(line.qty)}</span><button type="button" data-act="inc" data-id="${line.id}">+</button></div>
    <button type="button" class="btn danger" data-act="remove-line" data-id="${line.id}">حذف</button></div></div>`).join("") : `<p class="empty">سبد خالی است. بارکد را بخوانید یا کالا را انتخاب کنید.</p>`;
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
      <div class="field"><label>نام خریدار</label><input id="buyer-name" value="${esc(state.buyerName)}"></div>
      <div class="field"><label>شماره تماس</label><input id="buyer-phone" class="ltr" value="${esc(state.buyerPhone)}" placeholder="09..."></div>
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
  const rows = state.products.filter((product) => !query || `${product.name} ${product.barcode} ${product.sku}`.includes(query));
  if (!rows.length) return `<p class="empty">کالایی ثبت نشده. از فرم بالا یا فایل اکسل شروع کنید.</p>`;
  return `<table><thead><tr><th></th><th>نام</th><th>بارکد</th><th>قیمت فروش</th><th>موجودی</th><th></th></tr></thead><tbody>
    ${rows.map((product) => `<tr><td>${thumb(product.image, product.name, true)}</td><td>${esc(product.name)}${product.woo_id ? ` <span class="pill">ووکامرس</span>` : ""}</td><td class="ltr">${esc(product.barcode || "—")}</td><td class="num">${money(product.price)}</td><td class="num">${num(product.stock)} ${product.low ? `<span class="pill warn">کم</span>` : ""}</td><td class="row-actions"><button type="button" class="btn" data-act="edit-product" data-id="${product.id}">ویرایش</button><button type="button" class="btn danger" data-act="archive-product" data-id="${product.id}">بایگانی</button></td></tr>`).join("")}
  </tbody></table>`;
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
      <label class="btn">ورود اکسل<input id="excel-file" type="file" accept=".xlsx" hidden data-act="import-excel"></label>
      <button type="button" class="btn" data-act="woo-push">ارسال همه به ووکامرس</button>
      <button type="button" class="btn" data-act="woo-pull">دریافت از ووکامرس</button>
    </div><p class="hint">ستون‌های اکسل: نام، کد، بارکد، قیمت، موجودی، قیمت خرید، تصویر. سرستون انگلیسی هم قبول است. تصویر محلی فقط داخل دفترچی می‌ماند؛ ووکامرس آدرس اینترنتی می‌خواهد.</p></section>
    <section class="card"><input id="product-query" value="${esc(state.productQuery)}" placeholder="جستجو"><div id="product-table">${productRows()}</div></section>
  </div>`;
}

function inventoryHtml() {
  const data = state.inventory;
  if (!data) return "";
  const options = data.products.map((product) => `<option value="${product.id}">${esc(product.name)}</option>`).join("");
  const pay = data.pay_accounts.map((account) => `<option value="${esc(account.code)}">${esc(account.name)}</option>`).join("");
  return `<div class="stack"><section class="card"><table><thead><tr><th></th><th>کالا</th><th>قیمت</th><th>خرید</th><th>موجودی</th></tr></thead><tbody>
    ${data.products.map((product) => `<tr><td>${thumb(product.image, product.name, true)}</td><td>${esc(product.name)}</td><td class="num">${money(product.price)}</td><td class="num">${money(product.cost)}</td><td class="num">${num(product.stock)} ${product.low ? `<span class="pill warn">کم</span>` : ""}</td></tr>`).join("") || `<tr><td colspan="5">کالایی نیست.</td></tr>`}
  </tbody></table>
    <details><summary>تعدیل موجودی</summary><form data-act="adjust"><div class="field"><label>کالا</label><select name="product_id">${options}</select></div><div class="field"><label>موجودی جدید</label><input name="stock" inputmode="numeric" required></div><div class="field"><label>شرح</label><input name="note"></div><button class="btn primary" type="submit">ثبت</button></form></details>
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
    ["فروش درگاه", figures.gateway_sales], ["فروش نسیه", figures.credit_sales], ["لایسنس نقد", figures.license_cash],
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

function licensesHtml() {
  const data = state.licenses;
  if (!data) return "";
  const plans = data.plans.map((plan) => `<button type="button" class="plan ${state.plan === plan.id ? "on" : ""}" data-act="pick-plan" data-plan="${plan.id}"><span>${esc(plan.title)}</span><em class="num">${money(plan.price)}</em>${plan.remaining != null ? `<span>باقی‌مانده ${num(plan.remaining)} از ${num(plan.cap)}</span>` : ""}</button>`).join("");
  return `<div class="stack"><div class="plans">${plans}</div>
    <section class="card"><form data-act="sell-license"><input type="hidden" name="plan" value="${esc(state.plan)}">
      <div class="grid-2"><div class="field"><label>نام خریدار</label><input name="buyer_name" required></div><div class="field"><label>شماره تماس</label><input class="ltr" name="phone" required></div></div>
      <div class="grid-2"><div class="field"><label>تخفیف</label><input name="discount_value" value="0"></div><div class="field"><label>نوع تخفیف</label><select name="discount_type"><option value="amount">مبلغ</option><option value="percent">درصد</option></select></div></div>
      <div class="field"><label>پرداخت</label><select name="payment_method"><option value="cash">نقد</option><option value="card">کارت</option></select></div>
      <button class="btn primary" type="submit">ثبت لایسنس</button></form>
      <details><summary>قیمت‌ها و ظرفیت پنجاه‌ساله</summary><form data-act="save-prices"><div class="grid-2">
        ${[["price_3m", "سه ماهه"], ["price_6m", "شش ماهه"], ["price_12m", "یک ساله"], ["price_50y", "پنجاه ساله"], ["cap_50y", "ظرفیت پنجاه ساله"]].map(([key, label]) => {
          const plan = data.plans.find((item) => item.id === { price_3m: "3m", price_6m: "6m", price_12m: "12m", price_50y: "50y" }[key]);
          const value = key === "cap_50y" ? (data.plans.find((item) => item.id === "50y")?.cap ?? 50) : (plan?.price ?? "");
          return `<div class="field"><label>${label}</label><input name="${key}" value="${value}"></div>`;
        }).join("")}
      </div><button class="btn" type="submit">ذخیره قیمت‌ها</button></form></details>
    </section>
    <section class="card"><h2 class="section-title">لایسنس‌های فروخته‌شده</h2><table><thead><tr><th>طرح</th><th>خریدار</th><th>تماس</th><th>مبلغ</th><th>تا</th></tr></thead><tbody>
      ${data.licenses.map((row) => `<tr><td>${esc(row.title)}</td><td>${esc(row.buyer_name)}</td><td class="ltr">${esc(row.phone)}</td><td class="num">${money(row.payable)}</td><td>${esc(row.ends_jalali)}</td></tr>`).join("") || `<tr><td colspan="5">هنوز لایسنسی فروخته نشده.</td></tr>`}
    </tbody></table></section></div>`;
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
function field(key, label, type = "text") {
  return `<div class="field"><label>${label}</label><input name="${key}" type="${type}" value="${esc(state.settings[key] || "")}" ${type === "text" && /url|host|phone|sender|key|user/.test(key) ? `class="ltr"` : ""}></div>`;
}
function settingsHtml() {
  const s = state.settings;
  if (!s) return "";
  const checked = (key) => s[key] === "1" ? "checked" : "";
  return `<form class="stack" data-act="save-settings">
    <section class="card"><h2 class="section-title">وردپرس و ووکامرس</h2>
      ${field("wp_url", "آدرس سایت")}${field("woo_key", "Consumer key")}${field("woo_secret", "Consumer secret", "password")}
      <div class="row-actions"><button type="button" class="btn" data-act="test-setting" data-kind="wp">آزمایش وردپرس</button><button type="button" class="btn" data-act="test-setting" data-kind="woo">آزمایش ووکامرس</button></div>
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
      ${field("gateway_merchant", "شناسه پذیرنده")}${field("gateway_callback", "آدرس بازگشت")}
      <label class="check"><input type="checkbox" name="gateway_sandbox" ${checked("gateway_sandbox")}>حالت آزمایشی</label>
      <p class="hint">مبلغ‌ها در دفترچی تومان است و برای درگاه به ریال تبدیل می‌شود.</p>
    </section>
    <section class="card"><h2 class="section-title">پیامک</h2>
      <div class="field"><label>سامانه</label><select name="sms_provider">${options([["internal", "فقط داخل دفترچی"], ["kavenegar", "کاوه‌نگار"], ["melipayamak", "ملی‌پیامک"]], s.sms_provider)}</select></div>
      <div class="grid-2">${field("sms_api_key", "کلید کاوه‌نگار", "password")}${field("sms_sender", "شماره خط")}</div>
      <div class="grid-2">${field("sms_username", "نام کاربری ملی‌پیامک")}${field("sms_password", "رمز ملی‌پیامک", "password")}</div>
      ${field("manager_phone", "موبایل مدیر")}${field("low_stock", "آستانه موجودی کم")}
      <label class="check"><input type="checkbox" name="sms_on_close" ${checked("sms_on_close")}>پیامک بعد از بستن صندوق</label>
      <label class="check"><input type="checkbox" name="sms_on_sale" ${checked("sms_on_sale")}>پیامک هر فروش</label>
      <label class="check"><input type="checkbox" name="sms_low_stock" ${checked("sms_low_stock")}>پیامک موجودی کم</label>
      <button type="button" class="btn" data-act="test-setting" data-kind="sms">پیام آزمایشی</button>
    </section>
    <section class="card"><h2 class="section-title">جیمیل برای بازیابی رمز</h2>
      ${field("smtp_user", "آدرس جیمیل")}${field("smtp_password", "رمز برنامه جیمیل", "password")}
      <button type="button" class="btn" data-act="test-setting" data-kind="email">ایمیل آزمایشی</button>
      <p class="hint">در جیمیل باید App Password بسازید، نه رمز ورود معمولی.</p>
    </section>
    <button class="btn primary" type="submit">ذخیره تنظیمات</button>
  </form>
  <section class="card" style="margin-top:14px"><h2 class="section-title">ساخت اکانت</h2>
    <table><thead><tr><th>نام</th><th>موبایل</th><th>نقش</th></tr></thead><tbody>${state.users.map((user) => `<tr><td>${esc(user.name)}</td><td class="ltr">${esc(user.phone)}</td><td>${user.role === "admin" ? "مدیر" : "صندوقدار"}</td></tr>`).join("")}</tbody></table>
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
    <div class="field"><label>قیمت فروش، تومان</label><input name="price" inputmode="decimal" required autocomplete="off" value="${price}"></div>
    <div class="field"><label>موجودی</label><input name="stock" inputmode="numeric" autocomplete="off" value="${product.id ? product.stock : ""}"></div>
    <div class="field"><label>بارکد</label><input class="ltr" name="barcode" autocomplete="off" value="${esc(product.barcode || "")}"></div>
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
  if (modal.type === "card") inner = `<h2 class="section-title">کارت‌خوان</h2><p>${esc(modal.message || "")}</p><div class="field"><label>شماره پیگیری رسید</label><input id="pos-ref" class="ltr"></div><button type="button" class="btn primary" data-act="confirm-card">ثبت پرداخت کارت</button>`;
  if (modal.type === "gateway") inner = `<h2 class="section-title">پرداخت درگاهی</h2><p>فاکتور ${num(modal.sale.id)} · ${money(modal.sale.payable)}</p>${modal.sale.pay_url ? `<p><a href="${esc(modal.sale.pay_url)}" target="_blank" rel="noopener">باز کردن صفحه درگاه</a></p>` : ""}<div class="row-actions"><button type="button" class="btn primary" data-act="verify-sale" data-id="${modal.sale.id}">استعلام تأیید</button><button type="button" class="btn danger" data-act="cancel-sale" data-id="${modal.sale.id}">لغو</button></div><form data-act="manual-gateway"><input type="hidden" name="id" value="${modal.sale.id}"><div class="field"><label>اگر در پنل درگاه پرداخت را دیدید، پیگیری را بنویسید</label><input name="ref" required></div><button class="btn" type="submit">ثبت دستی</button></form>`;
  if (modal.type === "receipt") {
    const sale = modal.sale;
    inner = `<div id="print-area"><h2>دفترچی</h2><p>فاکتور ${num(sale.id)} · ${esc(sale.at_jalali)}</p><p>${esc(sale.customer_name || "")} ${esc(sale.customer_phone || "")}</p><table>${modal.items.map((item) => `<tr><td>${esc(item.name)} × ${num(item.qty)}</td><td class="num">${money(item.line_total)}</td></tr>`).join("")}</table><p>تخفیف ${money(sale.discount)}</p><p><strong>قابل پرداخت ${money(sale.payable)}</strong></p><p>${PAY[sale.payment_method] || ""}</p></div><button type="button" class="btn" data-act="print">چاپ</button>`;
  }
  if (modal.type === "password") inner = `<form data-act="change-password"><h2 class="section-title">تغییر رمز</h2><div class="field"><label>رمز فعلی</label><input type="password" name="current" required></div><div class="field"><label>رمز جدید</label><input type="password" name="password" minlength="6" required></div><button class="btn primary" type="submit">ذخیره</button></form>`;
  return `<div class="modal-back" data-act="close-modal"><div class="modal card" data-act="stop"><div class="row-actions"><button type="button" class="btn" data-act="close-modal">بستن</button></div>${inner}</div></div>`;
}

function pageHtml() {
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
  $app().innerHTML = shell(pageHtml()) + modalHtml();
  if (state.focusBarcode) {
    document.getElementById("barcode")?.focus();
    state.focusBarcode = false;
  }
}

async function onSubmit(event) {
  const form = event.target.closest("form[data-act]");
  if (!form) return;
  event.preventDefault();
  const act = form.dataset.act;
  const data = Object.fromEntries(new FormData(form).entries());
  await guard(async () => {
    if (act === "login") {
      const result = await api("/api/auth/login", { method: "POST", body: data });
      state.user = result.user;
      state.mustChange = result.must_change_password;
      await navigate("dashboard");
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
      data.plan = state.plan;
      const result = await api("/api/licenses", { method: "POST", body: data });
      toast(`لایسنس ثبت شد: ${money(result.payable)}`);
      await loaders.licenses();
      render();
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
  for (const key of ["gateway_sandbox", "sms_on_close", "sms_on_sale", "sms_low_stock"]) {
    data[key] = form.querySelector(`[name="${key}"]`)?.checked ? "1" : "0";
  }
  state.settings = (await api("/api/settings", { method: "PUT", body: data })).settings;
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
async function submitSale(method, posRef) {
  syncPos();
  if (!state.cart.length) return toast("سبد خالی است");
  const result = await api("/api/sales", {
    method: "POST",
    body: {
      items: state.cart.map((line) => ({ product_id: line.id, qty: line.qty })),
      discount_type: state.discountType,
      discount_value: state.discountType === "percent" ? Math.round(asInt(state.discountValue)) : asInt(state.discountValue),
      payment_method: method,
      customer_name: state.buyerName,
      customer_phone: state.buyerPhone,
      pos_ref: posRef || "",
    },
  });
  if (result.sale.status === "pending") {
    state.modal = { type: "gateway", sale: result.sale };
  } else {
    state.cart = [];
    state.discountValue = "";
    state.buyerName = "";
    state.buyerPhone = "";
    state.modal = { type: "receipt", sale: result.sale, items: result.items };
  }
  await loaders.pos();
  render();
}

async function onClick(event) {
  const el = event.target.closest("[data-act]");
  if (!el || el.closest("form[data-act]") && el.type === "submit") return;
  if (el.dataset.act === "stop") { event.stopPropagation(); return; }
  const act = el.dataset.act;
  if (act === "close-modal") { state.modal = null; render(); return; }
  if (act === "show-forgot") { state.authView = "forgot"; render(); return; }
  if (act === "show-login") { state.authView = "login"; render(); return; }
  if (act === "nav") { await guard(() => navigate(el.dataset.page)); return; }
  if (act === "chart") { state.chart = el.dataset.range; render(); return; }
  if (act === "pick-plan") { state.plan = el.dataset.plan; render(); return; }
  if (act === "print") { window.print(); return; }
  if (act === "password-modal") { state.modal = { type: "password" }; render(); return; }
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
    } else if (act === "inc" || act === "dec" || act === "remove-line") {
      syncPos();
      const line = state.cart.find((item) => item.id === Number(el.dataset.id));
      if (!line) return;
      if (act === "remove-line") state.cart = state.cart.filter((item) => item !== line);
      else if (act === "inc") {
        if (line.qty + 1 > line.stock) return toast("موجودی کافی نیست");
        line.qty += 1;
      } else line.qty -= 1;
      if (line.qty <= 0) state.cart = state.cart.filter((item) => item !== line);
      render();
    } else if (act === "pay") {
      syncPos();
      if (el.dataset.method === "card") {
        const prep = await api("/api/pos/prepare", { method: "POST", body: { amount: cartSubtotal() - cartDiscount() } });
        state.modal = { type: "card", message: prep.message, ok: prep.ok };
        render();
      } else await submitSale(el.dataset.method, "");
    } else if (act === "confirm-card") {
      await submitSale("card", document.getElementById("pos-ref")?.value || "");
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
      toast(`ووکامرس: ${num(result.created)} جدید، ${num(result.updated)} به‌روز`);
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
        state.modal = { type: "receipt", sale: result.sale, items: result.items };
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
    } else if (act === "filter-account") {
      state.accountId = el.dataset.id || "";
      await loaders.accounts();
      render();
    } else if (act === "test-setting") {
      const result = await api(`/api/settings/test/${el.dataset.kind}`, { method: "POST", body: {} });
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
    const box = document.getElementById("pos-grid");
    if (box) box.innerHTML = posTiles();
  }
  if (event.target.id === "product-query") {
    state.productQuery = event.target.value;
    const box = document.getElementById("product-table");
    if (box) box.innerHTML = productRows();
  }
}
function onChange(event) {
  if (event.target.id === "discount-type") refreshPayable();
  if (event.target.id === "excel-file" && event.target.files[0]) {
    const file = event.target.files[0];
    guard(async () => {
      const body = new FormData();
      body.append("file", file);
      state.importResult = await api("/api/products/import", { method: "POST", form: body });
      await loaders.products();
      toast("فایل اکسل خوانده شد");
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
window.addEventListener("hashchange", () => {
  const page = location.hash.replace("#", "");
  if (state.user && page && page !== state.page) guard(() => navigate(page));
});

api("/api/auth/me").then(async (me) => {
  if (!me.user) {
    state.bootstrap = await api("/api/auth/bootstrap");
    render();
    return;
  }
  state.user = me.user;
  state.mustChange = me.must_change_password;
  await navigate(location.hash.replace("#", "") || "dashboard");
}).catch((err) => {
  $app().innerHTML = `<p class="empty">${esc(err.message || "برنامه باز نشد")}</p>`;
});
