const API = "";

const fields = [
  ["doc_number", "№ документа"],
  ["doc_date", "Дата документа"],
  ["sender", "Отправитель"],
  ["sender_address", "Адрес отправителя"],
  ["receiver", "Получатель"],
  ["receiver_address", "Адрес получателя"],
  ["cargo_description", "Описание груза"],
  ["weight_kg", "Вес (кг)"],
  ["quantity", "Количество"],
  ["route", "Маршрут"],
  ["carrier", "Перевозчик"],
  ["notes", "Примечания"],
];

const labelMap = {
  document_type: "Тип документа",
  registration_number: "Регистрационный номер",
  doc_number: "№ документа",
  doc_date: "Дата документа",
  applicant: "Лицо, подающее ПИ",
  applicant_pin: "ПИН заявителя",
  pi_purpose: "Цель представления ПИ",
  arrival_checkpoint: "Пункт пропуска прибытия",
  arrival_checkpoint_code: "Код пункта пропуска",
  arrival_datetime: "Дата и время прибытия",
  origin_country: "Страна отправления",
  destination_country: "Страна назначения",
  customs_office: "Таможенный орган",
  customs_office_code: "Код таможенного органа",
  intermediate_country: "Промежуточная страна",
  carrier: "Перевозчик",
  carrier_id: "ID перевозчика",
  driver: "Водитель",
  driver_id: "ID водителя",
  submission_datetime: "Дата подачи",
  seal_number: "Номер пломбы",
  transport_doc_type: "Код транспортного документа",
  transport_doc_number: "Номер транспортного документа",
  transport_doc_date: "Дата выдачи транспортного документа",
  duty_payment_security: "Обеспечение уплаты пошлин",
  sender: "Отправитель",
  sender_name: "Наименование отправителя",
  sender_id: "ID отправителя",
  sender_address: "Адрес отправителя",
  receiver: "Получатель",
  receiver_name: "Наименование получателя",
  receiver_id: "ID получателя",
  receiver_address: "Адрес получателя",
  vehicles: "Транспортные средства",
  vehicle_registration_numbers: "Номера регистрации",
  vehicle_registration_numbers_text: "Номера регистрации",
  vehicle_registration_numbers_compact: "Номера ТС",
  vehicle_numbers: "Номера ТС",
  truck_registration_number: "Номер тягача",
  trailer_registration_number: "Номер прицепа",
  goods: "Товары",
  first_good_hs_code: "Н ВЭД",
  first_good_name: "Наименование товара",
  first_good_hs_code_and_name: "Н ВЭД и наименование",
  first_good_gross_weight_kg: "Масса брутто первого товара",
  first_good_unit: "ДЕИ",
  first_good_quantity: "Количество ДЕИ",
  first_good_currency_and_value: "Валюта и стоимость",
  first_good_country: "Страна",
  first_good_shipping_document: "Документы грузосопроводительные",
  invoice_number: "Номер инвойса",
  goods_count: "Количество наименований товаров",
  total_goods_count: "Количество товаров",
  total_net_weight_kg: "Общая масса нетто (кг)",
  total_gross_weight_kg: "Общая масса брутто (кг)",
  total_cargo_places: "Общее количество грузовых мест",
  total_value: "Общая стоимость товаров",
  cargo_description: "Описание груза",
  weight_kg: "Вес (кг)",
  quantity: "Количество",
  route: "Маршрут",
  carrier: "Перевозчик",
  notes: "Примечания",
  raw_text: "Сырой текст PDF",
};

const preferredFieldOrder = [
  "registration_number",
  "vehicle_registration_numbers_compact",
  "arrival_checkpoint",
  "customs_office",
  "sender",
  "receiver",
  "first_good_hs_code_and_name",
  "first_good_gross_weight_kg",
  "first_good_unit",
  "first_good_quantity",
  "first_good_currency_and_value",
  "first_good_country",
  "first_good_shipping_document",
  "total_goods_count",
  "total_net_weight_kg",
  "total_gross_weight_kg",
  "total_cargo_places",
  "invoice_number",
  "total_value",
];

function token() {
  return localStorage.getItem("access_token");
}

function currentRole() {
  return localStorage.getItem("role");
}

function authHeaders() {
  return { Authorization: `Bearer ${token()}` };
}

function requireAuth(adminOnly = false) {
  if (!token()) {
    window.location.href = "/";
    return false;
  }
  if (adminOnly && currentRole() !== "admin") {
    window.location.href = "/work.html";
    return false;
  }
  return true;
}

function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("role");
  localStorage.removeItem("name");
  window.location.href = "/";
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
  if (response.status === 401 || response.status === 403) {
    logout();
    throw new Error("Сессия закончилась");
  }
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Ошибка запроса");
  }
  return data;
}

function setStatus(element, message, kind = "") {
  element.textContent = message;
  element.className = `status ${kind}`.trim();
}

function fieldLabel(key) {
  return labelMap[key] || key.replaceAll("_", " ");
}

function orderedEntries(data) {
  if (data.document_type === "Предварительное информирование") {
    return preferredFieldOrder
      .filter((key) => key in data)
      .map((key) => [key, data[key]]);
  }
  const keys = Object.keys(data).filter((key) => !key.startsWith("_") && key !== "raw_text");
  const ordered = preferredFieldOrder.filter((key) => keys.includes(key));
  const rest = keys.filter((key) => !ordered.includes(key)).sort();
  return [...ordered, ...rest].map((key) => [key, data[key]]);
}

function valueToInputText(value) {
  if (Array.isArray(value) || (value && typeof value === "object")) {
    return JSON.stringify(value, null, 2);
  }
  return value ?? "";
}

function parseInputValue(input) {
  if (input.dataset.valueType === "json") {
    try {
      return JSON.parse(input.value || "null");
    } catch {
      return input.value;
    }
  }
  return input.value;
}

function initLogin() {
  const form = document.querySelector("#login-form");
  const status = document.querySelector("#login-status");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setStatus(status, "Вход...");
    const payload = Object.fromEntries(new FormData(form));
    try {
      const data = await apiFetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("role", data.role);
      localStorage.setItem("name", data.name);
      window.location.href = data.role === "admin" ? "/admin.html" : "/work.html";
    } catch (error) {
      setStatus(status, error.message, "error");
    }
  });
}

function initWork() {
  if (!document.querySelector("#dropzone") || !requireAuth()) return;

  const dropzone = document.querySelector("#dropzone");
  const fileInput = document.querySelector("#file-input");
  const draftButton = document.querySelector("#draft-button");
  const status = document.querySelector("#work-status");
  const fieldsForm = document.querySelector("#fields-form");
  const sendButton = document.querySelector("#send-button");
  const fileNameInput = document.querySelector("#filename");
  const adminLink = document.querySelector("#admin-link");
  const clientList = document.querySelector("#client-list");
  const clientForm = document.querySelector("#client-form");
  const clientInput = document.querySelector("#client-input");
  let currentExtractedData = {};
  let clients = [];
  let selectedClient = "";

  if (currentRole() === "admin") adminLink.classList.remove("hidden");
  document.querySelector("#user-name").textContent = localStorage.getItem("name") || "";

  function renderClients() {
    clientList.innerHTML = "";
    if (!clients.length) {
      const empty = document.createElement("div");
      empty.className = "muted-line";
      empty.textContent = "Добавьте клиента";
      clientList.append(empty);
      return;
    }

    clients.forEach((client) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = client.name === selectedClient ? "client-chip active" : "client-chip";
      button.textContent = client.name;
      button.addEventListener("click", () => {
        selectedClient = client.name;
        renderClients();
      });
      clientList.append(button);
    });
  }

  async function loadClients() {
    try {
      clients = await apiFetch("/clients", { headers: authHeaders() });
      if (!selectedClient && clients.length === 1) selectedClient = clients[0].name;
      renderClients();
    } catch (error) {
      setStatus(status, error.message, "error");
    }
  }

  function restoreDraft(draft) {
    currentExtractedData = draft.extracted_data || {};
    fileNameInput.value = draft.filename || "";
    if (currentExtractedData.client) selectedClient = currentExtractedData.client;
    renderClients();
    renderExtractedData(currentExtractedData);
    sendButton.disabled = false;
    setStatus(status, `Открыт черновик: ${draft.filename || "без имени"}`, "ok");
  }

  draftButton.addEventListener("click", async () => {
    try {
      const result = await apiFetch("/pdf/latest-draft", { headers: authHeaders() });
      if (!result.draft) {
        setStatus(status, "Неотправленных черновиков нет.", "warn");
        return;
      }
      restoreDraft(result.draft);
    } catch (error) {
      setStatus(status, error.message, "error");
    }
  });

  clientForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = clientInput.value.trim();
    if (!name) return;
    try {
      const client = await apiFetch("/clients", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      selectedClient = client.name;
      clientInput.value = "";
      await loadClients();
    } catch (error) {
      setStatus(status, error.message, "error");
    }
  });

  function renderExtractedData(data) {
    fieldsForm.innerHTML = "";
    orderedEntries(data).forEach(([key, value]) => {
      const isStructured = Array.isArray(value) || (value && typeof value === "object");
      const wrapper = document.createElement("label");
      if (isStructured || String(value ?? "").length > 80 || ["sender", "receiver", "raw_text", "notes"].includes(key)) {
        wrapper.classList.add("wide");
      }
      const input = isStructured || String(value ?? "").length > 80 ? document.createElement("textarea") : document.createElement("input");
      input.name = key;
      input.id = key;
      input.value = valueToInputText(value);
      input.dataset.valueType = isStructured ? "json" : "text";
      wrapper.textContent = fieldLabel(key);
      wrapper.classList.add("compact-field");
      wrapper.append(input);
      fieldsForm.append(wrapper);
    });
  }

  renderExtractedData(Object.fromEntries(fields.map(([key, label]) => [key, ""])));

  fields.forEach(([key]) => {
    const input = document.querySelector(`#${key}`);
    if (!input) return;
    input.name = key;
    input.id = key;
  });

  async function uploadFile(file) {
    if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
      setStatus(status, "Выберите PDF файл", "error");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    fileNameInput.value = file.name;
    setStatus(status, "Извлекаю данные из PDF...");
    try {
      const data = await apiFetch("/pdf/upload", {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      currentExtractedData = data;
      renderExtractedData(data);
      sendButton.disabled = false;
      setStatus(status, "Поля заполнены. Проверьте и отредактируйте при необходимости.", "ok");
    } catch (error) {
      setStatus(status, error.message, "error");
    }
  }

  dropzone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => uploadFile(fileInput.files[0]));
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-over");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-over");
    });
  });
  dropzone.addEventListener("drop", (event) => uploadFile(event.dataTransfer.files[0]));

  sendButton.addEventListener("click", async () => {
    if (!selectedClient) {
      setStatus(status, "Выберите клиента перед отправкой.", "error");
      return;
    }
    const extractedData = { ...currentExtractedData };
    fieldsForm.querySelectorAll("input, textarea, select").forEach((input) => {
      extractedData[input.name] = parseInputValue(input);
    });
    extractedData.client = selectedClient;
    extractedData.status = "Подан";
    setStatus(status, "Отправляю в Google Sheets...");
    try {
      const result = await apiFetch("/pdf/send-to-sheets", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ extracted_data: extractedData, filename: fileNameInput.value }),
      });
      if (result.success) {
        setStatus(status, "Данные отправлены в Google Sheets.", "ok");
      } else {
        setStatus(status, result.error || "Webhook не настроен или Google Sheets не принял запрос.", "warn");
      }
    } catch (error) {
      setStatus(status, error.message, "error");
    }
  });

  loadClients();
}

function row(cells) {
  const tr = document.createElement("tr");
  cells.forEach((cell) => {
    const td = document.createElement("td");
    if (cell instanceof Node) td.append(cell);
    else td.textContent = cell ?? "";
    tr.append(td);
  });
  return tr;
}

async function initAdmin() {
  if (!document.querySelector("#users-body") || !requireAuth(true)) return;

  const usersBody = document.querySelector("#users-body");
  const logsBody = document.querySelector("#logs-body");
  const status = document.querySelector("#admin-status");
  const form = document.querySelector("#user-form");
  document.querySelector("#user-name").textContent = localStorage.getItem("name") || "";

  async function loadUsers() {
    usersBody.innerHTML = "";
    const users = await apiFetch("/admin/users", { headers: authHeaders() });
    users.forEach((user) => {
      const button = document.createElement("button");
      button.className = "danger";
      button.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg> Удалить`;
      button.disabled = user.login === "admin";
      button.addEventListener("click", async () => {
        await apiFetch(`/admin/users/${user.id}`, { method: "DELETE", headers: authHeaders() });
        await loadUsers();
      });
      usersBody.append(row([user.name, user.login, user.role, user.created_at, button]));
    });
  }

  async function loadLogs() {
    logsBody.innerHTML = "";
    const logs = await apiFetch("/admin/logs", { headers: authHeaders() });
    logs.forEach((log) => {
      logsBody.append(row([
        log.user_name || "Удалённый пользователь",
        log.filename,
        log.sent_to_sheets ? "Да" : "Нет",
        log.created_at,
      ]));
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setStatus(status, "Создаю пользователя...");
    const payload = Object.fromEntries(new FormData(form));
    try {
      await apiFetch("/admin/users", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      form.reset();
      await loadUsers();
      setStatus(status, "Пользователь создан.", "ok");
    } catch (error) {
      setStatus(status, error.message, "error");
    }
  });

  try {
    await Promise.all([loadUsers(), loadLogs()]);
  } catch (error) {
    setStatus(status, error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-logout]").forEach((button) => button.addEventListener("click", logout));
  initLogin();
  initWork();
  initAdmin();
});
