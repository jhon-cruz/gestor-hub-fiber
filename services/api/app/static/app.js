"use strict";

const STATUS_OPTIONS = [
  ["planned", "Planejado"],
  ["under_construction", "Em construção"],
  ["active", "Ativo"],
  ["reserved", "Reservado"],
  ["damaged", "Danificado"],
  ["deactivated", "Desativado"],
];

const TYPE_LABELS = {
  cto: "CTO",
  pole: "Poste",
  splice_box: "Caixa de emenda",
  splitter: "Splitter",
  cable: "Cabo óptico",
  route: "Rota planejada",
  other: "Outro",
};

const TYPE_COLORS = {
  cto: "#0a9e72",
  pole: "#6f817d",
  splice_box: "#3578e5",
  splitter: "#7657d8",
  cable: "#d99529",
  route: "#2c7c70",
  other: "#607873",
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
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function setStatusOptions(select) {
  select.replaceChildren(...STATUS_OPTIONS.map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    return option;
  }));
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
  if (options.body && !(options.body instanceof URLSearchParams)) headers.set("Content-Type", "application/json");
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
  $("#current-username").textContent = state.user.username;
  $("#current-role").textContent = isAdmin ? "Administrador" : "Somente visualização";
  $("#user-avatar").textContent = state.user.username.slice(0, 1).toUpperCase();
  $("#auth-screen").classList.add("hidden");
  shell.classList.remove("hidden");
  initializeMap();
  window.setTimeout(() => state.map.invalidateSize(), 50);
  await loadFeatures(true);
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
}

function layerStyle(feature) {
  const type = feature.properties.feature_type;
  const color = TYPE_COLORS[type] || TYPE_COLORS.other;
  return {color, fillColor: color, weight: 4, opacity: .9, fillOpacity: .2};
}

function pointLayer(feature, latlng) {
  const color = TYPE_COLORS[feature.properties.feature_type] || TYPE_COLORS.other;
  return L.circleMarker(latlng, {
    radius: feature.properties.feature_type === "cto" ? 9 : 7,
    color: "#ffffff",
    weight: 2,
    fillColor: color,
    fillOpacity: 1,
  });
}

function renderFeatures(features = state.features) {
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
  updateStats();
}

async function loadFeatures(forceFit = false) {
  $("#map-loading").classList.remove("hidden");
  if (forceFit) state.hasFitBounds = false;
  try {
    const collection = await request("/api/v1/map-features?limit=1000");
    state.features = collection.features;
    renderFeatures();
    $("#map-summary").textContent = state.features.length
      ? `${state.features.length} ativo${state.features.length === 1 ? "" : "s"} carregado${state.features.length === 1 ? "" : "s"}`
      : "Nenhum ativo cadastrado — comece adicionando um ponto no mapa";
  } catch (error) {
    toast(error.message, "error");
  } finally {
    $("#map-loading").classList.add("hidden");
  }
}

function updateStats() {
  const count = (predicate) => state.features.filter(predicate).length;
  $("#stat-total").textContent = state.features.length;
  $("#stat-ctos").textContent = count((f) => f.properties.feature_type === "cto");
  $("#stat-routes").textContent = count((f) => ["cable", "route"].includes(f.properties.feature_type));
  $("#stat-planned").textContent = count((f) => f.properties.status === "planned");
  $("#stat-total-label").textContent = state.features.length === 1 ? "ativo geográfico" : "ativos geográficos";
}

function selectFeature(feature) {
  state.selected = feature;
  const props = feature.properties;
  $("#detail-title").textContent = props.name;
  $("#detail-name").value = props.name;
  $("#detail-type").value = TYPE_LABELS[props.feature_type] || props.feature_type;
  $("#detail-status").value = props.status;
  $("#detail-revision").textContent = props.revision;
  $("#detail-id").textContent = feature.id;
  $("#detail-name").readOnly = state.user.role !== "admin";
  $("#detail-status").disabled = state.user.role !== "admin";
  $("#feature-panel").classList.remove("hidden");
}

async function updateSelectedFeature(event) {
  event.preventDefault();
  if (!state.selected || state.user.role !== "admin") return;
  const form = event.currentTarget;
  setBusy(form, true);
  try {
    const updated = await request(`/api/v1/map-features/${state.selected.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: $("#detail-name").value.trim(),
        status: $("#detail-status").value,
        expected_revision: state.selected.properties.revision,
      }),
    });
    state.selected = updated;
    await loadFeatures();
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
      properties: {
        notes: $("#feature-notes").value.trim() || null,
        capacity: $("#feature-capacity").value ? Number($("#feature-capacity").value) : null,
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

function wireEvents() {
  $("#login-form").addEventListener("submit", handleLogin);
  $("#setup-form").addEventListener("submit", handleSetup);
  $("#logout-button").addEventListener("click", () => logout());
  $("#refresh-button").addEventListener("click", () => loadFeatures(true));
  $("#feature-search").addEventListener("input", () => renderFeatures());
  $("#add-feature-button").addEventListener("click", () => $("#feature-dialog").showModal());
  $("#feature-create-form").addEventListener("submit", beginDrawing);
  $("#finish-draw-button").addEventListener("click", finishDrawing);
  $("#cancel-draw-button").addEventListener("click", cancelDrawing);
  $("#feature-edit-form").addEventListener("submit", updateSelectedFeature);
  $("#delete-feature-button").addEventListener("click", deleteSelectedFeature);
  $("#close-detail-button").addEventListener("click", () => $("#feature-panel").classList.add("hidden"));
  $("#users-nav").addEventListener("click", openUsers);
  $("#user-create-form").addEventListener("submit", createUser);
  $("#menu-button").addEventListener("click", () => $("#app-shell").classList.toggle("menu-open"));
  $$(".modal-close").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
  $$(".password-toggle").forEach((button) => button.addEventListener("click", () => {
    const input = button.parentElement.querySelector("input");
    input.type = input.type === "password" ? "text" : "password";
    button.setAttribute("aria-label", input.type === "password" ? "Mostrar senha" : "Ocultar senha");
  }));
  $$(".nav-item[data-view]").forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.view !== "map") toast("Este módulo será liberado em uma próxima etapa.");
    $("#app-shell").classList.remove("menu-open");
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
  setStatusOptions($("#feature-status"));
  setStatusOptions($("#detail-status"));
  wireEvents();
  showInitialScreen();
});
