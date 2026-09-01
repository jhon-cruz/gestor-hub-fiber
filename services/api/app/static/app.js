"use strict";

const STATUS_OPTIONS = [
  ["planned", "Planejado"],
  ["under_construction", "Em construção"],
  ["active", "Ativo"],
  ["reserved", "Reservado"],
  ["damaged", "Danificado"],
  ["deactivated", "Desativado"],
];

const PORT_STATUS_OPTIONS = [
  ["available", "Disponível"],
  ["reserved", "Reservada"],
  ["occupied", "Ocupada"],
  ["damaged", "Danificada"],
  ["deactivated", "Desativada"],
];

const DEVICE_LABELS = {olt: "OLT", dio: "DIO", splitter: "Splitter", cto: "CTO"};
const CABLE_CLASS_LABELS = {
  feeder: "Feeder",
  distribution: "Distribuição",
  branch: "Derivação",
  drop: "Drop",
};
const FIBER_COLORS = {
  green: "#20a96b", yellow: "#f0c419", white: "#ffffff", blue: "#2387e8",
  red: "#e14c52", violet: "#7656c9", brown: "#8b5a3c", pink: "#ef8db6",
  black: "#1c2630", gray: "#8b99a7", orange: "#ee8a28", aqua: "#17c6d8",
};

const TYPE_LABELS = {
  cto: "CTO",
  pole: "Poste",
  splice_box: "Caixa de emenda",
  splitter: "Splitter",
  cable: "Cabo óptico",
  route: "Rota planejada",
  olt: "OLT",
  dio: "DIO",
  ont: "ONT/ONU",
  area: "Área",
  other: "Outro",
};

const TYPE_COLORS = {
  cto: "#008fff",
  pole: "#7f91a6",
  splice_box: "#17ceec",
  splitter: "#4f86c6",
  cable: "#00a9db",
  route: "#006fc7",
  other: "#607a92",
  olt: "#17ceec",
  dio: "#051a2c",
  ont: "#008fff",
  area: "#4f86c6",
};

const state = {
  token: sessionStorage.getItem("gestorHubToken"),
  user: null,
  features: [],
  map: null,
  featureGroup: null,
  layers: new Map(),
  selected: null,
  draw: null,
  draftLayer: null,
  hasFitBounds: false,
  importFile: null,
  importPreview: null,
  view: "map",
  networks: [],
  selectedNetworkId: localStorage.getItem("gestorHubNetworkId") || "",
  addressMarker: null,
  opticalDevices: [],
  selectedDevice: null,
  devicePorts: [],
  cables: [],
  selectedCable: null,
  cableFibers: [],
  fusionSourceFiber: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function preferredTheme() {
  const saved = localStorage.getItem("gestorHubTheme");
  if (["light", "dark"].includes(saved)) return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme, persist = false) {
  const isDark = theme === "dark";
  document.documentElement.dataset.theme = isDark ? "dark" : "light";
  const button = $("#theme-toggle");
  if (button) {
    button.setAttribute("aria-pressed", String(isDark));
    button.setAttribute("aria-label", isDark ? "Ativar tema claro" : "Ativar tema escuro");
    button.querySelector("span").textContent = isDark ? "☀" : "☾";
  }
  document.querySelector('meta[name="theme-color"]')?.setAttribute(
    "content", isDark ? "#03111e" : "#051a2c",
  );
  if (persist) localStorage.setItem("gestorHubTheme", isDark ? "dark" : "light");
}

function toggleTheme() {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark", true);
}

function setStatusOptions(select) {
  select.replaceChildren(...STATUS_OPTIONS.map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    return option;
  }));
}

function setTypeOptions(select) {
  select.replaceChildren(...Object.entries(TYPE_LABELS).map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    return option;
  }));
}

function setInventoryFilters() {
  const typeSelect = $("#inventory-type-filter");
  for (const [value, label] of Object.entries(TYPE_LABELS)) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    typeSelect.append(option);
  }
  const statusSelect = $("#inventory-status-filter");
  for (const [value, label] of STATUS_OPTIONS) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    statusSelect.append(option);
  }
}

function errorMessage(payload, fallback = "Não foi possível concluir a operação.") {
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) return payload.detail.map((item) => item.msg).join("; ");
  return fallback;
}

function translateError(message) {
  const messages = {
    "invalid username or password": "Usuário ou senha inválidos.",
    "installation already initialized": "A instalação já possui um administrador.",
    "username already exists": "Este nome de usuário já está em uso.",
    "stale feature revision": "Este ativo foi alterado por outra pessoa. O mapa será atualizado.",
    "administrator role required": "Esta ação exige acesso de administrador.",
  };
  return messages[message] || message;
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token && options.auth !== false) headers.set("Authorization", `Bearer ${state.token}`);
  if (
    options.body
    && !(options.body instanceof URLSearchParams)
    && !(options.body instanceof FormData)
  ) headers.set("Content-Type", "application/json");
  const response = await fetch(path, {...options, headers});
  if (response.status === 401 && options.auth !== false) {
    logout(false);
    throw new Error("Sua sessão expirou. Entre novamente.");
  }
  if (!response.ok) {
    let payload = {};
    try { payload = await response.json(); } catch { /* response without JSON */ }
    const error = new Error(translateError(errorMessage(payload)));
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

function toast(message, kind = "success") {
  const item = document.createElement("div");
  item.className = `toast ${kind}`;
  item.textContent = message;
  $("#toast-region").append(item);
  window.setTimeout(() => item.remove(), 4200);
}

function setBusy(form, busy) {
  const button = form.querySelector("button[type='submit']");
  if (!button) return;
  button.disabled = busy;
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = "Aguarde...";
  } else if (button.dataset.label) {
    button.textContent = button.dataset.label;
  }
}

function saveToken(token) {
  state.token = token;
  sessionStorage.setItem("gestorHubToken", token);
}

function logout(showMessage = true) {
  state.token = null;
  state.user = null;
  sessionStorage.removeItem("gestorHubToken");
  document.body.classList.remove("admin-mode", "viewer-mode");
  $("#app-shell").classList.add("hidden");
  $("#auth-screen").classList.remove("hidden");
  $("#login-form").classList.remove("hidden");
  $("#setup-form").classList.add("hidden");
  if (showMessage) toast("Sessão encerrada.");
}

async function showInitialScreen() {
  if (state.token) {
    try {
      await enterApplication();
      return;
    } catch (error) {
      sessionStorage.removeItem("gestorHubToken");
      state.token = null;
      if (error.status !== 401) toast(error.message, "error");
    }
  }
  try {
    const status = await request("/api/v1/auth/bootstrap-status", {auth: false});
    $("#setup-form").classList.toggle("hidden", !status.setup_required);
    $("#login-form").classList.toggle("hidden", status.setup_required);
  } catch (error) {
    $("#login-error").textContent = error.message;
  }
}

async function enterApplication() {
  state.user = await request("/api/v1/auth/me");
  const isAdmin = state.user.role === "admin";
  const shell = $("#app-shell");
  shell.classList.toggle("admin-mode", isAdmin);
  shell.classList.toggle("viewer-mode", !isAdmin);
  document.body.classList.toggle("admin-mode", isAdmin);
  document.body.classList.toggle("viewer-mode", !isAdmin);
  $("#current-username").textContent = state.user.username;
  $("#current-role").textContent = isAdmin ? "Administrador" : "Somente visualização";
  $("#user-avatar").textContent = state.user.username.slice(0, 1).toUpperCase();
  $("#auth-screen").classList.add("hidden");
  shell.classList.remove("hidden");
  initializeMap();
  window.setTimeout(() => state.map.invalidateSize(), 50);
  await loadFeatures(true);
  await Promise.all([loadNetworks(), loadOpticalDevices(), loadCables()]);
}

async function handleLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  $("#login-error").textContent = "";
  setBusy(form, true);
  const body = new URLSearchParams({
    username: $("#login-username").value.trim(),
    password: $("#login-password").value,
  });
  try {
    const token = await request("/api/v1/auth/token", {method: "POST", body, auth: false});
    saveToken(token.access_token);
    form.reset();
    await enterApplication();
  } catch (error) {
    $("#login-error").textContent = error.message;
  } finally {
    setBusy(form, false);
  }
}

async function handleSetup(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const password = $("#setup-password").value;
  $("#setup-error").textContent = "";
  if (password !== $("#setup-confirm").value) {
    $("#setup-error").textContent = "As senhas não coincidem.";
    return;
  }
  setBusy(form, true);
  try {
    const token = await request("/api/v1/auth/bootstrap", {
      method: "POST",
      auth: false,
      body: JSON.stringify({username: $("#setup-username").value.trim(), password}),
    });
    saveToken(token.access_token);
    form.reset();
    await enterApplication();
    toast("Administrador criado. Bem-vindo ao Gestor Hub Fiber!");
  } catch (error) {
    $("#setup-error").textContent = error.message;
  } finally {
    setBusy(form, false);
  }
}

function initializeMap() {
  if (state.map) return;
  if (!window.L) {
    $("#map-loading").textContent = "Não foi possível carregar a biblioteca do mapa. Verifique a internet.";
    return;
  }
  state.map = L.map("map", {zoomControl: false, preferCanvas: true}).setView([-14.235, -51.9253], 4);
  L.control.zoom({position: "bottomleft"}).addTo(state.map);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(state.map);
  state.featureGroup = L.featureGroup().addTo(state.map);
  state.map.on("click", handleMapClick);
  state.map.on("zoomend", updateMapMarkerDensity);
  updateMapMarkerDensity();
}

function updateMapMarkerDensity() {
  if (!state.map) return;
  const container = state.map.getContainer();
  const zoom = state.map.getZoom();
  container.classList.toggle("marker-density-wide", zoom <= 13);
  container.classList.toggle("marker-density-medium", zoom > 13 && zoom <= 15);
}

function layerStyle(feature) {
  const type = feature.properties.feature_type;
  const color = feature.properties.kml_style?.line_color || TYPE_COLORS[type] || TYPE_COLORS.other;
  return {color, fillColor: color, weight: 4, opacity: .9, fillOpacity: .2};
}

function pointLayer(feature, latlng) {
  const markerSymbols = {
    cto: '<rect x="8" y="9" width="20" height="18" rx="3"/><path d="M12 14h12M12 19h12M14 27v3M22 27v3"/>',
    splice_box: '<rect x="7" y="8" width="22" height="20" rx="7"/><path d="M11 13c5 0 5 10 10 10h4M11 23c5 0 5-10 10-10h4"/>',
    splitter: '<path d="M10 9h6v7m0 0v11m0-11h6v-4h5m-11 9h6v5h5"/><circle cx="10" cy="9" r="2"/><circle cx="29" cy="12" r="2"/><circle cx="29" cy="26" r="2"/>',
    olt: '<rect x="7" y="7" width="22" height="22" rx="3"/><path d="M11 12h14M11 17h14M11 22h8"/><circle cx="23" cy="22" r="1.5"/>',
    dio: '<rect x="6" y="10" width="24" height="17" rx="3"/><circle cx="12" cy="18.5" r="2"/><circle cx="18" cy="18.5" r="2"/><circle cx="24" cy="18.5" r="2"/>',
    ont: '<rect x="8" y="14" width="20" height="14" rx="3"/><path d="M13 14V9m10 5V9M13 10c3-3 7-3 10 0M12 23h12"/><circle cx="18" cy="19" r="1.5"/>',
  };
  const type = feature.properties.feature_type;
  if (markerSymbols[type]) {
    return L.marker(latlng, {
      icon: L.divIcon({
        className: `network-marker marker-${type}`,
        html: `<svg viewBox="0 0 36 36" aria-hidden="true"><circle class="marker-back" cx="18" cy="18" r="17"/><g class="marker-symbol">${markerSymbols[type]}</g></svg>`,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        popupAnchor: [0, -19],
      }),
      keyboard: true,
      title: feature.properties.name,
    });
  }
  const color = feature.properties.kml_style?.icon_color
    || TYPE_COLORS[type]
    || TYPE_COLORS.other;
  return L.circleMarker(latlng, {
    radius: 7,
    color: "#ffffff",
    weight: 2,
    fillColor: color,
    fillOpacity: 1,
  });
}

function selectedMapFeatures() {
  if (!state.selectedNetworkId) return state.features;
  return state.features.filter(
    (feature) => String(feature.properties.network_id || "") === state.selectedNetworkId,
  );
}

function renderFeatures(features = selectedMapFeatures()) {
  if (!state.featureGroup) return;
  state.featureGroup.clearLayers();
  state.layers.clear();
  const query = $("#feature-search").value.trim().toLowerCase();
  const visible = features.filter((feature) => {
    const props = feature.properties;
    return !query || `${props.name} ${props.feature_type} ${props.status}`.toLowerCase().includes(query);
  });
  for (const feature of visible) {
    const layer = L.geoJSON(feature, {style: layerStyle, pointToLayer: pointLayer}).getLayers()[0];
    if (!layer) continue;
    layer.on("click", () => selectFeature(feature));
    layer.bindTooltip(feature.properties.name, {direction: "top", offset: [0, -6]});
    state.featureGroup.addLayer(layer);
    state.layers.set(feature.id, layer);
  }
  if (!state.hasFitBounds && visible.length && state.featureGroup.getBounds().isValid()) {
    state.map.fitBounds(state.featureGroup.getBounds(), {padding: [90, 90], maxZoom: 16});
    state.hasFitBounds = true;
  }
  updateStats(features);
}

async function loadFeatures(forceFit = false) {
  $("#map-loading").classList.remove("hidden");
  if (forceFit) state.hasFitBounds = false;
  try {
    const collection = await request("/api/v1/map-features?limit=5000");
    state.features = collection.features;
    renderFeatures();
    renderInventory();
    const selected = selectedMapFeatures();
    $("#map-summary").textContent = selected.length
      ? `${selected.length} ativo${selected.length === 1 ? "" : "s"} carregado${selected.length === 1 ? "" : "s"}`
      : "Nenhum ativo cadastrado — comece adicionando um ponto no mapa";
  } catch (error) {
    toast(error.message, "error");
  } finally {
    $("#map-loading").classList.add("hidden");
  }
}

function updateStats(features = selectedMapFeatures()) {
  const count = (predicate) => features.filter(predicate).length;
  $("#stat-total").textContent = features.length;
  $("#stat-ctos").textContent = count((f) => f.properties.feature_type === "cto");
  $("#stat-routes").textContent = count((f) => ["cable", "route"].includes(f.properties.feature_type));
  $("#stat-planned").textContent = count((f) => f.properties.status === "planned");
  $("#stat-total-label").textContent = features.length === 1 ? "ativo geográfico" : "ativos geográficos";
}

function networkLabel(network) {
  const location = [network.city, network.state].filter(Boolean).join(" · ");
  return `${network.name}${location ? ` — ${location}` : ""} (${network.feature_count})`;
}

function populateNetworkSelect(select, emptyLabel) {
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = emptyLabel;
  select.replaceChildren(empty, ...state.networks.map((network) => {
    const option = document.createElement("option");
    option.value = network.id;
    option.textContent = networkLabel(network);
    return option;
  }));
}

function populateNetworkSources() {
  const select = $("#network-source");
  const sources = [...new Set(state.features
    .map((feature) => feature.properties.source_namespace)
    .filter(Boolean))].sort();
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "Nenhuma origem — usar a área visível do mapa";
  select.replaceChildren(empty, ...sources.map((source) => {
    const option = document.createElement("option");
    option.value = source;
    const count = state.features.filter(
      (feature) => feature.properties.source_namespace === source,
    ).length;
    option.textContent = `${source} (${count} elementos)`;
    return option;
  }));
}

async function loadNetworks() {
  try {
    state.networks = await request("/api/v1/networks");
    if (!state.networks.some((network) => network.id === state.selectedNetworkId)) {
      state.selectedNetworkId = "";
      localStorage.removeItem("gestorHubNetworkId");
    }
    populateNetworkSelect($("#network-select"), "Todas as redes");
    populateNetworkSelect($("#detail-network"), "Sem rede definida");
    populateNetworkSources();
    $("#network-select").value = state.selectedNetworkId;
    selectNetwork(state.selectedNetworkId, true);
  } catch (error) {
    toast(error.message, "error");
  }
}

function selectNetwork(networkId, moveMap = true) {
  state.selectedNetworkId = networkId || "";
  $("#network-select").value = state.selectedNetworkId;
  if (state.selectedNetworkId) localStorage.setItem("gestorHubNetworkId", state.selectedNetworkId);
  else localStorage.removeItem("gestorHubNetworkId");

  state.hasFitBounds = true;
  renderFeatures();
  const network = state.networks.find((item) => item.id === state.selectedNetworkId);
  const selected = selectedMapFeatures();
  const prefix = network ? `${network.name} · ` : "";
  $("#map-summary").textContent = `${prefix}${selected.length} ativo${selected.length === 1 ? "" : "s"}`;
  if (moveMap && network?.viewport?.length === 4 && state.map) {
    const [west, south, east, north] = network.viewport;
    state.map.fitBounds([[south, west], [north, east]], {padding: [100, 100], maxZoom: 16});
  } else if (moveMap && !network && selected.length && state.featureGroup.getBounds().isValid()) {
    state.map.fitBounds(state.featureGroup.getBounds(), {padding: [100, 100], maxZoom: 16});
  }
}

async function createNetwork(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const sourceNamespace = $("#network-source").value || null;
  const bounds = state.map.getBounds();
  $("#network-error").textContent = "";
  setBusy(form, true);
  try {
    const network = await request("/api/v1/networks", {
      method: "POST",
      body: JSON.stringify({
        name: $("#network-name").value.trim(),
        city: $("#network-city").value.trim(),
        state: $("#network-state").value.trim(),
        source_namespace: sourceNamespace,
        viewport: sourceNamespace ? null : [
          bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth(),
        ],
      }),
    });
    form.reset();
    $("#network-dialog").close();
    await loadFeatures(false);
    state.selectedNetworkId = network.id;
    await loadNetworks();
    selectNetwork(network.id, true);
    toast(`Rede “${network.name}” criada com ${network.feature_count} elementos.`);
  } catch (error) {
    $("#network-error").textContent = error.message;
  } finally {
    setBusy(form, false);
  }
}

function showAddressResult(result) {
  const [west, south, east, north] = result.viewport;
  state.map.fitBounds([[south, west], [north, east]], {padding: [120, 120], maxZoom: 18});
  if (state.addressMarker) state.map.removeLayer(state.addressMarker);
  state.addressMarker = L.circleMarker([result.latitude, result.longitude], {
    radius: 9,
    color: "#ffffff",
    weight: 3,
    fillColor: "#ff5b35",
    fillOpacity: 1,
  }).addTo(state.map).bindPopup(result.label).openPopup();
  $("#address-results").classList.add("hidden");
}

function renderAddressResults(payload) {
  const container = $("#address-results");
  if (!payload.results.length) {
    container.textContent = "Endereço não encontrado. Inclua rua, bairro, cidade e estado.";
    container.classList.remove("hidden");
    return;
  }
  const items = payload.results.map((result) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "address-result";
    const label = document.createElement("strong");
    label.textContent = result.label;
    const meta = document.createElement("small");
    meta.textContent = result.type || "Endereço";
    button.append(label, meta);
    button.addEventListener("click", () => showAddressResult(result));
    return button;
  });
  const attribution = document.createElement("small");
  attribution.className = "address-attribution";
  attribution.textContent = payload.attribution;
  container.replaceChildren(...items, attribution);
  container.classList.remove("hidden");
}

async function searchAddress(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const query = $("#address-search-input").value.trim();
  setBusy(form, true);
  try {
    const payload = await request(`/api/v1/geocoding/search?q=${encodeURIComponent(query)}`);
    renderAddressResults(payload);
  } catch (error) {
    $("#address-results").textContent = error.message;
    $("#address-results").classList.remove("hidden");
  } finally {
    setBusy(form, false);
  }
}

function statusLabel(value) {
  return STATUS_OPTIONS.find(([status]) => status === value)?.[1] || value;
}

function inventoryDescription(properties) {
  const description = properties.description || properties.notes || "";
  return String(description).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function renderInventory() {
  const body = $("#inventory-table-body");
  if (!body) return;
  const query = $("#inventory-search").value.trim().toLowerCase();
  const type = $("#inventory-type-filter").value;
  const status = $("#inventory-status-filter").value;
  const filtered = state.features.filter((feature) => {
    const properties = feature.properties;
    const searchable = [
      properties.name,
      properties.feature_type,
      properties.status,
      properties.source_namespace,
      properties.folder_path,
      inventoryDescription(properties),
    ].filter(Boolean).join(" ").toLowerCase();
    return (!query || searchable.includes(query))
      && (!type || properties.feature_type === type)
      && (!status || properties.status === status);
  });

  body.replaceChildren(...filtered.map((feature) => {
    const properties = feature.properties;
    const row = document.createElement("tr");
    const identityCell = document.createElement("td");
    const identity = document.createElement("div");
    identity.className = "inventory-identity";
    const dot = document.createElement("span");
    dot.className = "inventory-type-dot";
    dot.style.background = properties.kml_style?.icon_color
      || properties.kml_style?.line_color
      || TYPE_COLORS[properties.feature_type]
      || TYPE_COLORS.other;
    const text = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = properties.name;
    const description = document.createElement("small");
    description.textContent = inventoryDescription(properties) || `ID ${feature.id}`;
    text.append(name, description);
    identity.append(dot, text);
    identityCell.append(identity);

    const typeCell = document.createElement("td");
    typeCell.textContent = TYPE_LABELS[properties.feature_type] || properties.feature_type;
    const statusCell = document.createElement("td");
    const statusPill = document.createElement("span");
    statusPill.className = `status-pill ${properties.status}`;
    statusPill.textContent = statusLabel(properties.status);
    statusCell.append(statusPill);
    const capacityCell = document.createElement("td");
    const capacity = properties.fiber_count ?? properties.capacity;
    capacityCell.textContent = Number.isFinite(Number(capacity))
      && capacity !== null && capacity !== ""
      ? Number(capacity).toLocaleString("pt-BR")
      : "—";
    const originCell = document.createElement("td");
    originCell.className = "inventory-origin";
    originCell.textContent = properties.source_namespace || properties.folder_path || "Cadastro manual";
    const actionCell = document.createElement("td");
    const action = document.createElement("button");
    action.className = "button ghost inventory-open";
    action.type = "button";
    action.textContent = "Ver no mapa";
    action.addEventListener("click", () => openFeatureOnMap(feature));
    actionCell.append(action);
    row.append(identityCell, typeCell, statusCell, capacityCell, originCell, actionCell);
    return row;
  }));

  $("#inventory-empty").classList.toggle("hidden", filtered.length > 0);
  $("#inventory-result-count").textContent = `${filtered.length.toLocaleString("pt-BR")} resultado${filtered.length === 1 ? "" : "s"}`;
  $("#inventory-total").textContent = state.features.length.toLocaleString("pt-BR");
  $("#inventory-optical").textContent = state.features.filter((feature) =>
    ["cto", "splice_box", "splitter", "olt", "dio", "ont"].includes(feature.properties.feature_type)
  ).length.toLocaleString("pt-BR");
  $("#inventory-routes").textContent = state.features.filter((feature) =>
    ["cable", "route"].includes(feature.properties.feature_type)
  ).length.toLocaleString("pt-BR");
  $("#inventory-capacity").textContent = state.features.filter((feature) => {
    const capacity = feature.properties.fiber_count ?? feature.properties.capacity;
    return capacity !== null && capacity !== undefined;
  }).length.toLocaleString("pt-BR");
}

function portStatusLabel(value) {
  return PORT_STATUS_OPTIONS.find(([status]) => status === value)?.[1] || value;
}

function renderOpticalDevices() {
  const body = $("#device-table-body");
  if (!body) return;
  const query = $("#device-search").value.trim().toLowerCase();
  const type = $("#device-type-filter").value;
  const filtered = state.opticalDevices.filter((device) => {
    const searchable = [device.name, device.manufacturer, device.model, device.serial_number]
      .filter(Boolean).join(" ").toLowerCase();
    return (!query || searchable.includes(query)) && (!type || device.device_type === type);
  });

  body.replaceChildren(...filtered.map((device) => {
    const row = document.createElement("tr");
    const identityCell = document.createElement("td");
    const identity = document.createElement("div");
    identity.className = "inventory-identity";
    const dot = document.createElement("span");
    dot.className = "inventory-type-dot";
    dot.style.background = TYPE_COLORS[device.device_type] || TYPE_COLORS.other;
    const text = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = device.name;
    const meta = document.createElement("small");
    meta.textContent = [device.manufacturer, device.model].filter(Boolean).join(" · ")
      || (device.map_feature_id ? "Vinculado ao mapa" : "Sem vínculo geográfico");
    text.append(name, meta);
    identity.append(dot, text);
    identityCell.append(identity);

    const typeCell = document.createElement("td");
    typeCell.textContent = DEVICE_LABELS[device.device_type] || device.device_type;
    const statusCell = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = `status-pill ${device.status}`;
    pill.textContent = statusLabel(device.status);
    statusCell.append(pill);
    const portsCell = document.createElement("td");
    portsCell.textContent = device.port_summary.total.toLocaleString("pt-BR");
    const occupationCell = document.createElement("td");
    const percentage = device.port_summary.total
      ? Math.round((device.port_summary.occupied / device.port_summary.total) * 100)
      : 0;
    occupationCell.textContent = `${device.port_summary.occupied} ocupadas · ${percentage}%`;
    const actionCell = document.createElement("td");
    const action = document.createElement("button");
    action.className = "button ghost inventory-open";
    action.type = "button";
    action.textContent = "Ver portas";
    action.addEventListener("click", () => openDevice(device));
    actionCell.append(action);
    row.append(identityCell, typeCell, statusCell, portsCell, occupationCell, actionCell);
    return row;
  }));

  const totals = state.opticalDevices.reduce((summary, device) => ({
    total: summary.total + device.port_summary.total,
    occupied: summary.occupied + device.port_summary.occupied,
    available: summary.available + device.port_summary.available,
  }), {total: 0, occupied: 0, available: 0});
  $("#device-total").textContent = state.opticalDevices.length.toLocaleString("pt-BR");
  $("#device-ports-total").textContent = totals.total.toLocaleString("pt-BR");
  $("#device-ports-occupied").textContent = totals.occupied.toLocaleString("pt-BR");
  $("#device-ports-available").textContent = totals.available.toLocaleString("pt-BR");
  $("#device-result-count").textContent = `${filtered.length} resultado${filtered.length === 1 ? "" : "s"}`;
  $("#device-empty").classList.toggle("hidden", filtered.length > 0);
}

async function loadOpticalDevices() {
  try {
    state.opticalDevices = await request("/api/v1/optical-devices?limit=2000");
    renderOpticalDevices();
    populateDeviceFeatureOptions();
  } catch (error) {
    toast(error.message, "error");
  }
}

function populateDeviceFeatureOptions() {
  const select = $("#new-device-feature");
  if (!select) return;
  const type = $("#new-device-type").value;
  const eligible = state.features.filter((feature) =>
    feature.properties.feature_type === type && !feature.properties.optical_device_id
  );
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "Sem vínculo geográfico";
  select.replaceChildren(empty, ...eligible.map((feature) => {
    const option = document.createElement("option");
    option.value = feature.id;
    option.textContent = feature.properties.name;
    return option;
  }));
}

async function createOpticalDevice(event) {
  event.preventDefault();
  const form = event.currentTarget;
  $("#device-create-error").textContent = "";
  setBusy(form, true);
  try {
    const device = await request("/api/v1/optical-devices", {
      method: "POST",
      body: JSON.stringify({
        map_feature_id: $("#new-device-feature").value || null,
        device_type: $("#new-device-type").value,
        name: $("#new-device-name").value.trim(),
        status: $("#new-device-status").value,
        manufacturer: $("#new-device-manufacturer").value.trim() || null,
        model: $("#new-device-model").value.trim() || null,
        serial_number: $("#new-device-serial").value.trim() || null,
        port_capacity: Number($("#new-device-capacity").value),
        properties: {},
      }),
    });
    form.reset();
    setStatusOptions($("#new-device-status"));
    $("#new-device-capacity").value = "16";
    $("#device-create-dialog").close();
    await Promise.all([loadFeatures(false), loadOpticalDevices()]);
    await openDevice(device);
    toast("Equipamento e portas criados.");
  } catch (error) {
    $("#device-create-error").textContent = error.message;
  } finally {
    setBusy(form, false);
  }
}

function renderDevicePorts() {
  const list = $("#device-ports-list");
  list.replaceChildren(...state.devicePorts.map((port) => {
    const row = document.createElement("article");
    row.className = "device-port-row";
    const identity = document.createElement("div");
    identity.className = "device-port-identity";
    const name = document.createElement("strong");
    name.className = `port-state ${port.status}`;
    name.textContent = port.label || `Porta ${port.position}`;
    const kind = document.createElement("small");
    kind.textContent = `${port.port_kind.replaceAll("_", " ")} · posição ${port.position}`;
    identity.append(name, kind);
    const select = document.createElement("select");
    for (const [value, label] of PORT_STATUS_OPTIONS) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.append(option);
    }
    select.value = port.status;
    select.disabled = state.user.role !== "admin";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button ghost small admin-only";
    button.textContent = "Salvar";
    button.addEventListener("click", () => updateOpticalPort(port, select.value, button));
    row.append(identity, select, button);
    return row;
  }));
}

async function openDevice(device) {
  state.selectedDevice = device;
  $("#device-detail-title").textContent = `${DEVICE_LABELS[device.device_type]} · ${device.name}`;
  $("#device-detail-name").value = device.name;
  $("#device-detail-status").value = device.status;
  $("#device-detail-manufacturer").value = device.manufacturer || "";
  $("#device-detail-model").value = device.model || "";
  $("#device-detail-serial").value = device.serial_number || "";
  $("#device-detail-capacity").value = `${device.port_summary.total} portas`;
  $("#device-map-button").classList.toggle("hidden", !device.map_feature_id);
  const canEdit = state.user.role === "admin";
  for (const selector of ["#device-detail-name", "#device-detail-manufacturer", "#device-detail-model", "#device-detail-serial"]) {
    $(selector).readOnly = !canEdit;
  }
  $("#device-detail-status").disabled = !canEdit;
  $("#device-ports-summary").textContent = "Carregando portas...";
  $("#device-ports-list").innerHTML = '<span class="field-hint">Carregando...</span>';
  $("#device-detail-dialog").showModal();
  try {
    state.devicePorts = await request(`/api/v1/optical-devices/${device.id}/ports`);
    $("#device-ports-summary").textContent = [
      `${device.port_summary.available} disponíveis`,
      `${device.port_summary.occupied} ocupadas`,
      `${device.port_summary.reserved} reservadas`,
    ].join(" · ");
    renderDevicePorts();
  } catch (error) {
    $("#device-ports-list").textContent = error.message;
  }
}

async function updateOpticalDevice(event) {
  event.preventDefault();
  if (!state.selectedDevice || state.user.role !== "admin") return;
  const form = event.currentTarget;
  setBusy(form, true);
  try {
    const updated = await request(`/api/v1/optical-devices/${state.selectedDevice.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: $("#device-detail-name").value.trim(),
        status: $("#device-detail-status").value,
        manufacturer: $("#device-detail-manufacturer").value.trim() || null,
        model: $("#device-detail-model").value.trim() || null,
        serial_number: $("#device-detail-serial").value.trim() || null,
        expected_revision: state.selectedDevice.revision,
      }),
    });
    state.selectedDevice = updated;
    await loadOpticalDevices();
    toast("Equipamento atualizado.");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setBusy(form, false);
  }
}

async function updateOpticalPort(port, status, button) {
  button.disabled = true;
  try {
    const updated = await request(`/api/v1/optical-ports/${port.id}`, {
      method: "PATCH",
      body: JSON.stringify({status, expected_revision: port.revision}),
    });
    state.devicePorts = state.devicePorts.map((item) => item.id === updated.id ? updated : item);
    await loadOpticalDevices();
    const fresh = state.opticalDevices.find((device) => device.id === state.selectedDevice.id);
    if (fresh) state.selectedDevice = fresh;
    renderDevicePorts();
    toast(`Porta marcada como ${portStatusLabel(status).toLowerCase()}.`);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

function openSelectedDeviceOnMap() {
  if (!state.selectedDevice?.map_feature_id) return;
  const feature = state.features.find((item) => item.id === state.selectedDevice.map_feature_id);
  if (!feature) return toast("O item geográfico vinculado não está disponível.", "error");
  $("#device-detail-dialog").close();
  openFeatureOnMap(feature);
}

function renderCables() {
  const body = $("#cable-table-body");
  if (!body) return;
  const query = $("#cable-search").value.trim().toLowerCase();
  const cableClass = $("#cable-class-filter").value;
  const filtered = state.cables.filter((cable) =>
    (!query || cable.name.toLowerCase().includes(query))
      && (!cableClass || cable.cable_class === cableClass)
  );
  body.replaceChildren(...filtered.map((cable) => {
    const row = document.createElement("tr");
    const identityCell = document.createElement("td");
    const identity = document.createElement("div");
    identity.className = "inventory-identity";
    const dot = document.createElement("span");
    dot.className = "inventory-type-dot";
    dot.style.background = TYPE_COLORS.cable;
    const text = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = cable.name;
    const meta = document.createElement("small");
    meta.textContent = cable.map_feature_id ? "Vinculado ao mapa" : "Sem vínculo geográfico";
    text.append(name, meta);
    identity.append(dot, text);
    identityCell.append(identity);
    const classCell = document.createElement("td");
    classCell.textContent = CABLE_CLASS_LABELS[cable.cable_class] || cable.cable_class;
    const structureCell = document.createElement("td");
    structureCell.textContent = `${cable.tube_count} tubos × ${cable.fibers_per_tube} fibras`;
    const fibersCell = document.createElement("td");
    fibersCell.textContent = `${cable.fiber_count} FO`;
    const availabilityCell = document.createElement("td");
    availabilityCell.textContent = `${cable.fiber_summary.available} livres · ${cable.fiber_summary.occupied} ocupadas`;
    const actionCell = document.createElement("td");
    const action = document.createElement("button");
    action.className = "button ghost inventory-open";
    action.type = "button";
    action.textContent = "Ver fibras";
    action.addEventListener("click", () => openCable(cable));
    actionCell.append(action);
    row.append(identityCell, classCell, structureCell, fibersCell, availabilityCell, actionCell);
    return row;
  }));
  const totals = state.cables.reduce((summary, cable) => ({
    fibers: summary.fibers + cable.fiber_summary.total,
    available: summary.available + cable.fiber_summary.available,
    occupied: summary.occupied + cable.fiber_summary.occupied,
  }), {fibers: 0, available: 0, occupied: 0});
  $("#cable-total").textContent = state.cables.length.toLocaleString("pt-BR");
  $("#fiber-total").textContent = totals.fibers.toLocaleString("pt-BR");
  $("#fiber-available").textContent = totals.available.toLocaleString("pt-BR");
  $("#fiber-occupied").textContent = totals.occupied.toLocaleString("pt-BR");
  $("#cable-result-count").textContent = `${filtered.length} resultado${filtered.length === 1 ? "" : "s"}`;
  $("#cable-empty").classList.toggle("hidden", filtered.length > 0);
}

async function loadCables() {
  try {
    state.cables = await request("/api/v1/optical-cables?limit=2000");
    renderCables();
    populateCableFeatureOptions();
  } catch (error) {
    toast(error.message, "error");
  }
}

function populateCableFeatureOptions() {
  const select = $("#new-cable-feature");
  if (!select) return;
  const eligible = state.features.filter((feature) =>
    ["cable", "route"].includes(feature.properties.feature_type)
      && !feature.properties.optical_cable_id
  );
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "Sem vínculo geográfico";
  select.replaceChildren(empty, ...eligible.map((feature) => {
    const option = document.createElement("option");
    option.value = feature.id;
    option.textContent = `${feature.properties.name} · ${feature.properties.fiber_count ?? feature.properties.capacity ?? "?"} FO`;
    return option;
  }));
}

async function createCable(event) {
  event.preventDefault();
  const form = event.currentTarget;
  $("#cable-create-error").textContent = "";
  setBusy(form, true);
  try {
    const cable = await request("/api/v1/optical-cables", {
      method: "POST",
      body: JSON.stringify({
        network_id: state.selectedNetworkId || null,
        map_feature_id: $("#new-cable-feature").value || null,
        name: $("#new-cable-name").value.trim(),
        cable_class: $("#new-cable-class").value,
        status: $("#new-cable-status").value,
        fiber_count: Number($("#new-cable-fibers").value),
        tube_count: Number($("#new-cable-tubes").value),
        fibers_per_tube: Number($("#new-cable-fibers-per-tube").value),
        technical_reserve_m: Number($("#new-cable-reserve").value || 0),
        properties: {},
      }),
    });
    form.reset();
    setStatusOptions($("#new-cable-status"));
    $("#new-cable-fibers").value = "24";
    $("#new-cable-tubes").value = "2";
    $("#new-cable-fibers-per-tube").value = "12";
    $("#cable-create-dialog").close();
    await Promise.all([loadFeatures(false), loadCables()]);
    await openCable(cable);
    toast(`${cable.fiber_count} fibras criadas em ${cable.tube_count} tubos.`);
  } catch (error) {
    $("#cable-create-error").textContent = error.message;
  } finally {
    setBusy(form, false);
  }
}

function fiberLabel(fiber) {
  return `FO ${fiber.global_position} · tubo ${fiber.tube_position}/${fiber.tube_color} · ${fiber.color_code}`;
}

function renderCableFibers() {
  const list = $("#cable-fibers-list");
  list.replaceChildren(...state.cableFibers.map((fiber) => {
    const row = document.createElement("article");
    row.className = "fiber-row";
    const identity = document.createElement("div");
    identity.className = "fiber-identity";
    const color = document.createElement("span");
    color.className = "fiber-color";
    color.style.setProperty("--fiber-color", FIBER_COLORS[fiber.color_code.split("-")[0]] || "#7f91a6");
    const text = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = `Fibra ${fiber.global_position}`;
    const meta = document.createElement("small");
    const connected = fiber.connected_ends?.length ? ` · conectada ${fiber.connected_ends.join("/").toUpperCase()}` : "";
    meta.textContent = `Tubo ${fiber.tube_position} · ${fiber.color_code}${connected}`;
    text.append(name, meta);
    identity.append(color, text);
    const select = document.createElement("select");
    for (const [value, label] of PORT_STATUS_OPTIONS) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.append(option);
    }
    select.value = fiber.status;
    select.disabled = state.user.role !== "admin";
    const save = document.createElement("button");
    save.type = "button";
    save.className = "button ghost small admin-only";
    save.textContent = "Salvar";
    save.addEventListener("click", () => updateFiber(fiber, select.value, save));
    const fuse = document.createElement("button");
    fuse.type = "button";
    fuse.className = "button ghost small admin-only";
    fuse.textContent = "Fusão";
    fuse.addEventListener("click", () => openFusion(fiber));
    row.append(identity, select, save, fuse);
    return row;
  }));
}

async function openCable(cable) {
  state.selectedCable = cable;
  $("#cable-detail-title").textContent = cable.name;
  $("#cable-detail-class").textContent = CABLE_CLASS_LABELS[cable.cable_class];
  $("#cable-detail-structure").textContent = `${cable.tube_count} × ${cable.fibers_per_tube}`;
  $("#cable-detail-available").textContent = `${cable.fiber_summary.available}/${cable.fiber_summary.total}`;
  $("#cable-map-button").classList.toggle("hidden", !cable.map_feature_id);
  $("#cable-fibers-summary").textContent = "Carregando fibras...";
  $("#cable-fibers-list").innerHTML = '<span class="field-hint">Carregando...</span>';
  $("#cable-detail-dialog").showModal();
  try {
    state.cableFibers = await request(`/api/v1/optical-cables/${cable.id}/fibers`);
    $("#cable-fibers-summary").textContent = `${state.cableFibers.length} fibras em ${cable.tube_count} tubos`;
    renderCableFibers();
  } catch (error) {
    $("#cable-fibers-list").textContent = error.message;
  }
}

async function updateFiber(fiber, status, button) {
  button.disabled = true;
  try {
    const updated = await request(`/api/v1/optical-fibers/${fiber.id}`, {
      method: "PATCH",
      body: JSON.stringify({status, expected_revision: fiber.revision}),
    });
    state.cableFibers = state.cableFibers.map((item) => item.id === updated.id
      ? {...item, ...updated}
      : item);
    await loadCables();
    const fresh = state.cables.find((item) => item.id === state.selectedCable.id);
    if (fresh) state.selectedCable = fresh;
    renderCableFibers();
    toast(`Fibra marcada como ${portStatusLabel(status).toLowerCase()}.`);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function openFusion(fiber) {
  state.fusionSourceFiber = fiber;
  $("#fusion-source-label").value = `${state.selectedCable.name} · ${fiberLabel(fiber)}`;
  const enclosures = state.features.filter((feature) =>
    ["splice_box", "cto", "dio", "splitter"].includes(feature.properties.feature_type)
  );
  $("#fusion-enclosure").replaceChildren(...enclosures.map((feature) => {
    const option = document.createElement("option");
    option.value = feature.id;
    option.textContent = feature.properties.name;
    return option;
  }));
  $("#fusion-target-cable").replaceChildren(...state.cables.map((cable) => {
    const option = document.createElement("option");
    option.value = cable.id;
    option.textContent = cable.name;
    return option;
  }));
  $("#fusion-target-cable").value = state.cables.find((item) => item.id !== state.selectedCable.id)?.id
    || state.selectedCable.id;
  $("#fusion-error").textContent = "";
  await loadFusionTargetFibers();
  $("#fusion-dialog").showModal();
}

async function loadFusionTargetFibers() {
  const cableId = $("#fusion-target-cable").value;
  if (!cableId) return;
  try {
    const fibers = await request(`/api/v1/optical-cables/${cableId}/fibers`);
    $("#fusion-target-fiber").replaceChildren(...fibers
      .filter((fiber) => fiber.id !== state.fusionSourceFiber?.id)
      .map((fiber) => {
        const option = document.createElement("option");
        option.value = fiber.id;
        option.textContent = fiberLabel(fiber);
        return option;
      }));
  } catch (error) {
    $("#fusion-error").textContent = error.message;
  }
}

async function createFusion(event) {
  event.preventDefault();
  const form = event.currentTarget;
  $("#fusion-error").textContent = "";
  setBusy(form, true);
  try {
    await request("/api/v1/fiber-connections", {
      method: "POST",
      body: JSON.stringify({
        enclosure_feature_id: $("#fusion-enclosure").value,
        connection_type: "fusion",
        loss_db: Number($("#fusion-loss").value),
        notes: $("#fusion-notes").value.trim() || null,
        endpoints: [
          {fiber_id: state.fusionSourceFiber.id, end_side: $("#fusion-source-side").value},
          {fiber_id: $("#fusion-target-fiber").value, end_side: $("#fusion-target-side").value},
        ],
      }),
    });
    form.reset();
    $("#fusion-loss").value = "0.1";
    $("#fusion-dialog").close();
    state.cableFibers = await request(`/api/v1/optical-cables/${state.selectedCable.id}/fibers`);
    renderCableFibers();
    toast("Fusão registrada com integridade de extremidades.");
  } catch (error) {
    $("#fusion-error").textContent = error.message;
  } finally {
    setBusy(form, false);
  }
}

function openSelectedCableOnMap() {
  if (!state.selectedCable?.map_feature_id) return;
  const feature = state.features.find((item) => item.id === state.selectedCable.map_feature_id);
  if (!feature) return toast("O traçado vinculado não está disponível.", "error");
  $("#cable-detail-dialog").close();
  openFeatureOnMap(feature);
}

function showView(view) {
  if (!["map", "inventory", "optical", "fibers"].includes(view)) return;
  state.view = view;
  $("#map-view").classList.toggle("hidden", view !== "map");
  $("#inventory-view").classList.toggle("hidden", view !== "inventory");
  $("#optical-view").classList.toggle("hidden", view !== "optical");
  $("#fibers-view").classList.toggle("hidden", view !== "fibers");
  $$(".nav-item[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  const labels = {
    map: ["Mapa da rede", "Visão geográfica"],
    inventory: ["Inventário", "Ativos da rede"],
    optical: ["Equipamentos", "Domínio óptico"],
    fibers: ["Cabos e fibras", "Topologia física"],
  };
  $("#topbar-section").textContent = labels[view][0];
  $("#topbar-title").textContent = labels[view][1];
  $("#feature-search").closest(".search-box").classList.toggle("hidden", view !== "map");
  $("#refresh-button").setAttribute(
    "aria-label", view === "map" ? "Atualizar mapa" : "Atualizar inventário",
  );
  $("#app-shell").classList.remove("menu-open");
  if (view === "map") {
    window.setTimeout(() => state.map?.invalidateSize(), 30);
  } else if (view === "inventory") {
    renderInventory();
  } else if (view === "optical") {
    renderOpticalDevices();
  } else {
    renderCables();
  }
}

function openFeatureOnMap(feature) {
  $("#feature-search").value = "";
  state.selectedNetworkId = String(feature.properties.network_id || "");
  if (state.selectedNetworkId) localStorage.setItem("gestorHubNetworkId", state.selectedNetworkId);
  else localStorage.removeItem("gestorHubNetworkId");
  $("#network-select").value = state.selectedNetworkId;
  renderFeatures();
  showView("map");
  selectFeature(feature);
  const layer = state.layers.get(feature.id);
  if (layer?.getLatLng) state.map.setView(layer.getLatLng(), Math.max(state.map.getZoom(), 17));
  else if (layer?.getBounds && layer.getBounds().isValid()) {
    state.map.fitBounds(layer.getBounds(), {padding: [100, 100], maxZoom: 17});
  }
}

function selectFeature(feature) {
  state.selected = feature;
  const props = feature.properties;
  $("#detail-title").textContent = props.name;
  $("#detail-name").value = props.name;
  $("#detail-type").value = props.feature_type;
  $("#detail-status").value = props.status;
  $("#detail-network").value = props.network_id || "";
  $("#detail-fiber-count").value = props.fiber_count ?? props.capacity ?? "";
  toggleFiberField();
  $("#detail-revision").textContent = props.revision;
  $("#detail-id").textContent = feature.id;
  $("#detail-name").readOnly = state.user.role !== "admin";
  $("#detail-type").disabled = state.user.role !== "admin";
  $("#detail-status").disabled = state.user.role !== "admin";
  $("#detail-network").disabled = state.user.role !== "admin";
  $("#detail-fiber-count").readOnly = state.user.role !== "admin";
  $("#feature-panel").classList.remove("hidden");
}

function toggleFiberField() {
  $("#detail-fiber-field").classList.toggle(
    "hidden", !["cable", "route"].includes($("#detail-type").value),
  );
}

async function updateSelectedFeature(event) {
  event.preventDefault();
  if (!state.selected || state.user.role !== "admin") return;
  const form = event.currentTarget;
  setBusy(form, true);
  try {
    const type = $("#detail-type").value;
    const properties = {...state.selected.properties};
    for (const key of ["name", "status", "feature_type", "revision", "fiberq_uuid", "network_id"]) {
      delete properties[key];
    }
    if (["cable", "route"].includes(type)) {
      properties.fiber_count = $("#detail-fiber-count").value
        ? Number($("#detail-fiber-count").value)
        : null;
    } else {
      delete properties.fiber_count;
    }
    const updated = await request(`/api/v1/map-features/${state.selected.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: $("#detail-name").value.trim(),
        feature_type: type,
        status: $("#detail-status").value,
        network_id: $("#detail-network").value || null,
        properties,
        expected_revision: state.selected.properties.revision,
      }),
    });
    state.selected = updated;
    await loadFeatures();
    await loadNetworks();
    selectFeature(updated);
    toast("Ativo atualizado.");
  } catch (error) {
    toast(error.message, "error");
    if (error.status === 409) {
      $("#feature-panel").classList.add("hidden");
      await loadFeatures();
    }
  } finally {
    setBusy(form, false);
  }
}

async function deleteSelectedFeature() {
  if (!state.selected || state.user.role !== "admin") return;
  const name = state.selected.properties.name;
  if (!window.confirm(`Excluir “${name}”? Esta ação ficará registrada na auditoria.`)) return;
  try {
    await request(`/api/v1/map-features/${state.selected.id}`, {method: "DELETE"});
    state.selected = null;
    $("#feature-panel").classList.add("hidden");
    await loadFeatures();
    toast("Ativo excluído.");
  } catch (error) {
    toast(error.message, "error");
  }
}

function beginDrawing(event) {
  event.preventDefault();
  state.draw = {
    geometryType: $("#geometry-type").value,
    points: [],
    payload: {
      name: $("#feature-name").value.trim(),
      feature_type: $("#feature-type").value,
      status: $("#feature-status").value,
      network_id: state.selectedNetworkId || null,
      properties: {
        notes: $("#feature-notes").value.trim() || null,
        capacity: $("#feature-capacity").value ? Number($("#feature-capacity").value) : null,
        fiber_count: ["cable", "route"].includes($("#feature-type").value)
          && $("#feature-capacity").value
          ? Number($("#feature-capacity").value)
          : null,
      },
    },
  };
  $("#feature-dialog").close();
  const isPoint = state.draw.geometryType === "Point";
  $("#draw-title").textContent = isPoint ? "Posicione o ativo" : "Desenhe o traçado";
  $("#draw-help").textContent = isPoint
    ? "Clique no local exato para salvar."
    : "Clique para adicionar vértices e conclua quando terminar.";
  $("#finish-draw-button").classList.toggle("hidden", isPoint);
  $("#draw-toolbar").classList.remove("hidden");
  $("#map").classList.add("drawing-cursor");
  $("#feature-panel").classList.add("hidden");
}

function handleMapClick(event) {
  if (!state.draw) return;
  state.draw.points.push(event.latlng);
  if (state.draw.geometryType === "Point") {
    saveDrawnFeature({type: "Point", coordinates: [event.latlng.lng, event.latlng.lat]});
    return;
  }
  if (state.draftLayer) state.map.removeLayer(state.draftLayer);
  const style = {color: TYPE_COLORS[state.draw.payload.feature_type] || TYPE_COLORS.other, weight: 4, dashArray: "7 6"};
  state.draftLayer = state.draw.geometryType === "Polygon"
    ? L.polygon(state.draw.points, style).addTo(state.map)
    : L.polyline(state.draw.points, style).addTo(state.map);
  $("#draw-help").textContent = `${state.draw.points.length} vértice${state.draw.points.length === 1 ? "" : "s"} marcado${state.draw.points.length === 1 ? "" : "s"}.`;
}

function finishDrawing() {
  if (!state.draw) return;
  const minimum = state.draw.geometryType === "Polygon" ? 3 : 2;
  if (state.draw.points.length < minimum) {
    toast(`Marque pelo menos ${minimum} pontos para concluir.`, "error");
    return;
  }
  const coordinates = state.draw.points.map((point) => [point.lng, point.lat]);
  if (state.draw.geometryType === "Polygon") coordinates.push([...coordinates[0]]);
  const geometry = state.draw.geometryType === "Polygon"
    ? {type: "Polygon", coordinates: [coordinates]}
    : {type: "LineString", coordinates};
  saveDrawnFeature(geometry);
}

async function saveDrawnFeature(geometry) {
  const payload = {...state.draw.payload, geometry};
  try {
    const created = await request("/api/v1/map-features", {method: "POST", body: JSON.stringify(payload)});
    cancelDrawing();
    $("#feature-create-form").reset();
    setStatusOptions($("#feature-status"));
    await loadFeatures();
    selectFeature(created);
    toast("Ativo adicionado ao mapa.");
  } catch (error) {
    toast(error.message, "error");
  }
}

function cancelDrawing() {
  state.draw = null;
  if (state.draftLayer && state.map) state.map.removeLayer(state.draftLayer);
  state.draftLayer = null;
  $("#draw-toolbar").classList.add("hidden");
  $("#map").classList.remove("drawing-cursor");
}

async function openUsers() {
  if (state.user.role !== "admin") return;
  $("#users-dialog").showModal();
  await loadUsers();
}

async function loadUsers() {
  const list = $("#users-list");
  list.innerHTML = '<span class="spinner"></span>';
  try {
    const users = await request("/api/v1/users");
    list.replaceChildren(...users.map((user) => {
      const row = document.createElement("article");
      row.className = "user-row";
      const avatar = document.createElement("div");
      avatar.className = "avatar";
      avatar.textContent = user.username.slice(0, 1).toUpperCase();
      const identity = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = user.username;
      const meta = document.createElement("small");
      meta.textContent = user.is_active ? "Conta ativa" : "Conta inativa";
      identity.append(name, meta);
      const role = document.createElement("span");
      role.className = `role-badge ${user.role}`;
      role.textContent = user.role === "admin" ? "Admin" : "Visualização";
      row.append(avatar, identity, role);
      return row;
    }));
  } catch (error) {
    list.textContent = error.message;
  }
}

async function createUser(event) {
  event.preventDefault();
  const form = event.currentTarget;
  $("#user-create-error").textContent = "";
  setBusy(form, true);
  try {
    await request("/api/v1/users", {
      method: "POST",
      body: JSON.stringify({
        username: $("#new-username").value.trim(),
        password: $("#new-password").value,
        role: $("#new-role").value,
      }),
    });
    form.reset();
    await loadUsers();
    toast("Usuário criado com sucesso.");
  } catch (error) {
    $("#user-create-error").textContent = error.message;
  } finally {
    setBusy(form, false);
  }
}

function normalizeImportNamespace(filename) {
  return filename
    .replace(/\.kmz$/i, "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^[-._]+|[-._]+$/g, "")
    .slice(0, 120);
}

function handleKmzFile(event) {
  const [file] = event.currentTarget.files;
  state.importFile = file || null;
  state.importPreview = null;
  $("#kmz-preview").classList.add("hidden");
  $("#kmz-empty-state").classList.remove("hidden");
  $("#kmz-error").textContent = "";
  if (!file) {
    $("#kmz-file-label").textContent = "Selecione um arquivo .kmz";
    return;
  }
  $("#kmz-file-label").textContent = `${file.name} · ${(file.size / 1024).toFixed(0)} KB`;
  $("#kmz-namespace").value = normalizeImportNamespace(file.name);
}

function importFormData() {
  const data = new FormData();
  data.append("file", state.importFile);
  data.append("source_namespace", $("#kmz-namespace").value.trim());
  data.append("default_status", $("#kmz-default-status").value);
  if (state.selectedNetworkId) data.append("network_id", state.selectedNetworkId);
  return data;
}

function renderImportPreview(preview) {
  state.importPreview = preview;
  $("#kmz-preview-name").textContent = preview.filename;
  $("#kmz-total").textContent = preview.feature_count.toLocaleString("pt-BR");
  $("#kmz-new").textContent = preview.new_count.toLocaleString("pt-BR");
  $("#kmz-updates").textContent = preview.update_count.toLocaleString("pt-BR");
  const badge = $("#kmz-preview-badge");
  badge.textContent = preview.already_imported ? "Já importado" : "Pronto";
  badge.classList.toggle("viewer", preview.already_imported);

  const breakdown = $("#kmz-breakdown");
  breakdown.replaceChildren(...Object.entries(preview.type_counts).map(([type, count]) => {
    const item = document.createElement("span");
    item.className = "breakdown-item";
    const label = document.createTextNode(`${TYPE_LABELS[type] || type} `);
    const value = document.createElement("strong");
    value.textContent = count.toLocaleString("pt-BR");
    item.append(label, value);
    return item;
  }));

  const warningBox = $("#kmz-warning-box");
  warningBox.classList.toggle("hidden", !preview.warnings.length);
  $("#kmz-warnings").replaceChildren(...preview.warnings.slice(0, 8).map((warning) => {
    const item = document.createElement("li");
    item.textContent = warning.message;
    return item;
  }));
  const importButton = $("#kmz-import-button");
  importButton.disabled = preview.already_imported;
  importButton.textContent = preview.already_imported
    ? "Este arquivo já foi importado"
    : `Confirmar importação de ${preview.feature_count.toLocaleString("pt-BR")} elementos`;
  $("#kmz-preview").classList.remove("hidden");
  $("#kmz-empty-state").classList.add("hidden");
}

async function previewKmz(event) {
  event.preventDefault();
  const form = event.currentTarget;
  $("#kmz-error").textContent = "";
  if (!state.importFile) {
    $("#kmz-error").textContent = "Selecione um arquivo KMZ.";
    return;
  }
  if (state.importFile.size > 20 * 1024 * 1024) {
    $("#kmz-error").textContent = "O arquivo excede o limite de 20 MB.";
    return;
  }
  setBusy(form, true);
  try {
    const preview = await request("/api/v1/imports/kmz/preview", {
      method: "POST",
      body: importFormData(),
    });
    renderImportPreview(preview);
  } catch (error) {
    $("#kmz-error").textContent = error.message;
    $("#kmz-preview").classList.add("hidden");
    $("#kmz-empty-state").classList.remove("hidden");
  } finally {
    setBusy(form, false);
  }
}

async function confirmKmzImport() {
  if (!state.importFile || !state.importPreview || state.importPreview.already_imported) return;
  const button = $("#kmz-import-button");
  button.disabled = true;
  const label = button.textContent;
  button.textContent = "Importando e validando geometrias...";
  try {
    const result = await request("/api/v1/imports/kmz", {
      method: "POST",
      body: importFormData(),
    });
    button.textContent = "Importação concluída";
    $("#kmz-preview-badge").textContent = "Importado";
    toast(
      `${result.created_count.toLocaleString("pt-BR")} novos e ${result.updated_count.toLocaleString("pt-BR")} atualizados.`,
    );
    await Promise.all([loadFeatures(true), loadImportHistory()]);
    await loadNetworks();
    if (state.importPreview.bounds && state.map) {
      const [west, south, east, north] = state.importPreview.bounds;
      state.map.fitBounds([[south, west], [north, east]], {padding: [80, 80]});
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = label;
    toast(error.message, "error");
  }
}

async function openImports() {
  if (state.user.role !== "admin") return;
  $("#imports-dialog").showModal();
  await loadImportHistory();
}

async function loadImportHistory() {
  const container = $("#imports-history");
  container.innerHTML = '<span class="field-hint">Carregando histórico...</span>';
  try {
    const imports = await request("/api/v1/imports");
    if (!imports.length) {
      container.innerHTML = '<span class="field-hint">Nenhuma importação registrada.</span>';
      return;
    }
    container.replaceChildren(...imports.map((item) => {
      const row = document.createElement("article");
      row.className = "import-history-row";
      const identity = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = item.filename;
      const meta = document.createElement("small");
      meta.textContent = `${item.source_namespace} · ${new Date(item.created_at).toLocaleString("pt-BR")}`;
      identity.append(name, meta);
      const total = document.createElement("span");
      total.textContent = `${item.feature_count.toLocaleString("pt-BR")} elementos`;
      const result = document.createElement("span");
      result.textContent = `+${item.created_count} / ↻${item.updated_count}`;
      row.append(identity, total, result);
      return row;
    }));
  } catch (error) {
    container.textContent = error.message;
  }
}

function wireEvents() {
  $("#login-form").addEventListener("submit", handleLogin);
  $("#setup-form").addEventListener("submit", handleSetup);
  $("#logout-button").addEventListener("click", () => logout());
  $("#refresh-button").addEventListener("click", () => {
    if (state.view === "optical") loadOpticalDevices();
    else if (state.view === "fibers") loadCables();
    else loadFeatures(state.view === "map");
  });
  $("#theme-toggle").addEventListener("click", toggleTheme);
  $("#feature-search").addEventListener("input", () => renderFeatures());
  $("#network-select").addEventListener("change", (event) => selectNetwork(event.target.value));
  $("#add-network-button").addEventListener("click", () => $("#network-dialog").showModal());
  $("#network-create-form").addEventListener("submit", createNetwork);
  $("#address-search-form").addEventListener("submit", searchAddress);
  $("#add-feature-button").addEventListener("click", () => $("#feature-dialog").showModal());
  $("#feature-create-form").addEventListener("submit", beginDrawing);
  $("#finish-draw-button").addEventListener("click", finishDrawing);
  $("#cancel-draw-button").addEventListener("click", cancelDrawing);
  $("#feature-edit-form").addEventListener("submit", updateSelectedFeature);
  $("#detail-type").addEventListener("change", toggleFiberField);
  $("#delete-feature-button").addEventListener("click", deleteSelectedFeature);
  $("#close-detail-button").addEventListener("click", () => $("#feature-panel").classList.add("hidden"));
  $("#users-nav").addEventListener("click", openUsers);
  $("#imports-nav").addEventListener("click", openImports);
  $("#user-create-form").addEventListener("submit", createUser);
  $("#kmz-file").addEventListener("change", handleKmzFile);
  $("#kmz-preview-form").addEventListener("submit", previewKmz);
  $("#kmz-import-button").addEventListener("click", confirmKmzImport);
  $("#refresh-imports-button").addEventListener("click", loadImportHistory);
  $("#inventory-search").addEventListener("input", renderInventory);
  $("#inventory-type-filter").addEventListener("change", renderInventory);
  $("#inventory-status-filter").addEventListener("change", renderInventory);
  $("#inventory-map-button").addEventListener("click", () => showView("map"));
  $("#device-search").addEventListener("input", renderOpticalDevices);
  $("#device-type-filter").addEventListener("change", renderOpticalDevices);
  $("#add-device-button").addEventListener("click", () => {
    populateDeviceFeatureOptions();
    $("#device-create-dialog").showModal();
  });
  $("#new-device-type").addEventListener("change", () => {
    const defaults = {cto: 16, splitter: 8, dio: 24, olt: 8};
    $("#new-device-capacity").value = defaults[$("#new-device-type").value];
    populateDeviceFeatureOptions();
  });
  $("#new-device-feature").addEventListener("change", (event) => {
    const feature = state.features.find((item) => item.id === event.target.value);
    if (feature) $("#new-device-name").value = feature.properties.name;
  });
  $("#device-create-form").addEventListener("submit", createOpticalDevice);
  $("#device-edit-form").addEventListener("submit", updateOpticalDevice);
  $("#device-map-button").addEventListener("click", openSelectedDeviceOnMap);
  $("#cable-search").addEventListener("input", renderCables);
  $("#cable-class-filter").addEventListener("change", renderCables);
  $("#add-cable-button").addEventListener("click", () => {
    populateCableFeatureOptions();
    $("#cable-create-dialog").showModal();
  });
  $("#new-cable-feature").addEventListener("change", (event) => {
    const feature = state.features.find((item) => item.id === event.target.value);
    if (!feature) return;
    $("#new-cable-name").value = feature.properties.name;
    const capacity = Number(feature.properties.fiber_count ?? feature.properties.capacity);
    if (Number.isInteger(capacity) && capacity > 0) {
      $("#new-cable-fibers").value = capacity;
      $("#new-cable-tubes").value = Math.ceil(capacity / 12);
    }
  });
  $("#cable-create-form").addEventListener("submit", createCable);
  $("#cable-map-button").addEventListener("click", openSelectedCableOnMap);
  $("#fusion-target-cable").addEventListener("change", loadFusionTargetFibers);
  $("#fusion-form").addEventListener("submit", createFusion);
  $("#menu-button").addEventListener("click", () => $("#app-shell").classList.toggle("menu-open"));
  $$(".modal-close").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
  $$(".password-toggle").forEach((button) => button.addEventListener("click", () => {
    const input = button.parentElement.querySelector("input");
    input.type = input.type === "password" ? "text" : "password";
    button.setAttribute("aria-label", input.type === "password" ? "Mostrar senha" : "Ocultar senha");
  }));
  $$(".nav-item[data-view]").forEach((button) => button.addEventListener("click", () => {
    if (["map", "inventory", "optical", "fibers"].includes(button.dataset.view)) showView(button.dataset.view);
    else {
      toast("Este módulo será liberado em uma próxima etapa.");
      $("#app-shell").classList.remove("menu-open");
    }
  }));
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      $("#feature-search").focus();
    }
    if (event.key === "Escape" && state.draw) cancelDrawing();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(preferredTheme());
  setStatusOptions($("#feature-status"));
  setStatusOptions($("#detail-status"));
  setStatusOptions($("#kmz-default-status"));
  setStatusOptions($("#new-device-status"));
  setStatusOptions($("#device-detail-status"));
  setStatusOptions($("#new-cable-status"));
  setTypeOptions($("#detail-type"));
  setInventoryFilters();
  wireEvents();
  showInitialScreen();
});
