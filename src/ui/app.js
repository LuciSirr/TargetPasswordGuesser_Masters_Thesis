const state = {
  defaults: null,
  currentPage: "profile",
};

function setStatus(message, tone = "") {
  const box = document.getElementById("status");
  box.textContent = message;
  box.className = `status ${tone}`.trim();
}

function showPage(page) {
  state.currentPage = page;
  document.querySelectorAll(".page-card").forEach((element) => {
    element.classList.toggle("active", element.id === `page-${page}`);
  });
  document.querySelectorAll(".menu-button").forEach((element) => {
    element.classList.toggle("active", element.id === `menu-${page}`);
  });
}

function linesToList(value) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeInt(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function normalizeFloat(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number.parseFloat(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function addRepeatItem(templateId, containerId, values = {}) {
  const template = document.getElementById(templateId);
  const container = document.getElementById(containerId);
  const node = template.content.firstElementChild.cloneNode(true);

  node.querySelectorAll("[data-field]").forEach((input) => {
    const key = input.dataset.field;
    input.value = values[key] ?? "";
    input.addEventListener("input", renderPreviews);
  });

  node.querySelector("[data-remove]").addEventListener("click", () => {
    node.remove();
    renderPreviews();
  });

  container.appendChild(node);
  renderPreviews();
}

function addChild(values = {}) {
  addRepeatItem("childTemplate", "childrenList", values);
}

function addPet(values = {}) {
  addRepeatItem("petTemplate", "petsList", values);
}

function collectRepeatItems(containerId) {
  const container = document.getElementById(containerId);
  return [...container.children]
    .map((item) => {
      const entry = {};
      item.querySelectorAll("[data-field]").forEach((input) => {
        entry[input.dataset.field] = input.value.trim();
      });
      return entry;
    })
    .filter((entry) => Object.values(entry).some(Boolean));
}

function collectProfile() {
  const profile = {
    self_first_name: document.getElementById("self_first_name").value.trim(),
    self_last_name: document.getElementById("self_last_name").value.trim(),
    partner_first_name: document.getElementById("partner_first_name").value.trim(),
    partner_last_name: document.getElementById("partner_last_name").value.trim(),
    birth_date: document.getElementById("birth_date").value.trim(),
    age: normalizeInt(document.getElementById("age").value),
    nationality: document.getElementById("nationality").value.trim(),
    region: document.getElementById("region").value.trim(),
    company: document.getElementById("company").value.trim(),
    car_brand: document.getElementById("car_brand").value.trim(),
    interests: linesToList(document.getElementById("interests").value),
    previous_passwords: linesToList(document.getElementById("previous_passwords").value),
    children: collectRepeatItems("childrenList"),
    pets: collectRepeatItems("petsList"),
  };

  Object.keys(profile).forEach((key) => {
    if (profile[key] === null) {
      delete profile[key];
    }
  });

  return profile;
}

function collectRuntimeConfig() {
  return {
    model_training: {
      max_password_length: normalizeInt(document.getElementById("max_password_length").value),
      embedding_fallback_threshold: normalizeFloat(document.getElementById("embedding_fallback_threshold").value),
    },
    generation: {
      mode: document.getElementById("generation_mode").value,
      unique: document.getElementById("generation_unique").value === "true",
    },
    token_enhancement: {
      dbpedia: {
        graph_depth: normalizeInt(document.getElementById("graph_depth").value),
        graph_width: normalizeInt(document.getElementById("graph_width").value),
        threshold_dbp: normalizeFloat(document.getElementById("threshold_dbp").value),
        category_weight: normalizeFloat(document.getElementById("category_weight").value),
        type_weight: normalizeFloat(document.getElementById("type_weight").value),
        request_timeout: normalizeInt(document.getElementById("request_timeout").value),
        request_delay: normalizeFloat(document.getElementById("request_delay").value),
      },
      embeddings: {
        threshold_w2v: normalizeFloat(document.getElementById("threshold_w2v").value),
        threshold_fasttext: normalizeFloat(document.getElementById("threshold_fasttext").value),
      },
      max_expansion: normalizeInt(document.getElementById("max_expansion").value),
    },
  };
}

function collectResourcesConfig() {
  return {
    dbpedia_sparql_url: document.getElementById("dbpedia_sparql_url").value.trim(),
    languages: {
      en: {
        w2v_model: document.getElementById("en_w2v_model").value.trim(),
        fasttext_model: document.getElementById("en_fasttext_model").value.trim(),
      },
      cz: {
        w2v_model: document.getElementById("cz_w2v_model").value.trim(),
        fasttext_model: document.getElementById("cz_fasttext_model").value.trim(),
        name_diminutives: document.getElementById("cz_name_diminutives").value.trim(),
      },
      de: {
        w2v_model: document.getElementById("de_w2v_model").value.trim(),
        fasttext_model: document.getElementById("de_fasttext_model").value.trim(),
      },
    },
  };
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed with ${response.status}`);
  }
  return data;
}

function assignProfile(profile) {
  document.getElementById("self_first_name").value = profile.self_first_name ?? "";
  document.getElementById("self_last_name").value = profile.self_last_name ?? "";
  document.getElementById("partner_first_name").value = profile.partner_first_name ?? "";
  document.getElementById("partner_last_name").value = profile.partner_last_name ?? "";
  document.getElementById("birth_date").value = profile.birth_date ?? profile.birthday ?? "";
  document.getElementById("age").value = profile.age ?? "";
  document.getElementById("nationality").value = profile.nationality ?? "";
  document.getElementById("region").value = profile.region ?? "";
  document.getElementById("company").value = profile.company ?? "";
  document.getElementById("car_brand").value = profile.car_brand ?? "";
  document.getElementById("interests").value = (profile.interests ?? []).join("\n");
  document.getElementById("previous_passwords").value = (profile.previous_passwords ?? []).join("\n");

  const childrenList = document.getElementById("childrenList");
  const petsList = document.getElementById("petsList");
  childrenList.innerHTML = "";
  petsList.innerHTML = "";

  (profile.children ?? []).forEach(addChild);
  (profile.pets ?? []).forEach(addPet);
  renderPreviews();
}

function assignRuntimeConfig(config) {
  const modelTraining = config.model_training ?? {};
  const generation = config.generation ?? {};
  const tokenEnhancement = config.token_enhancement ?? {};
  const dbpedia = tokenEnhancement.dbpedia ?? {};
  const embeddings = tokenEnhancement.embeddings ?? {};

  document.getElementById("max_password_length").value = modelTraining.max_password_length ?? "";
  document.getElementById("embedding_fallback_threshold").value = modelTraining.embedding_fallback_threshold ?? "";
  document.getElementById("generation_mode").value = generation.mode ?? "deterministic";
  document.getElementById("generation_unique").value = String(generation.unique ?? true);
  document.getElementById("graph_depth").value = dbpedia.graph_depth ?? "";
  document.getElementById("graph_width").value = dbpedia.graph_width ?? "";
  document.getElementById("threshold_dbp").value = dbpedia.threshold_dbp ?? "";
  document.getElementById("category_weight").value = dbpedia.category_weight ?? "";
  document.getElementById("type_weight").value = dbpedia.type_weight ?? "";
  document.getElementById("request_timeout").value = dbpedia.request_timeout ?? "";
  document.getElementById("request_delay").value = dbpedia.request_delay ?? "";
  document.getElementById("threshold_w2v").value = embeddings.threshold_w2v ?? "";
  document.getElementById("threshold_fasttext").value = embeddings.threshold_fasttext ?? "";
  document.getElementById("max_expansion").value = tokenEnhancement.max_expansion ?? "";
  renderPreviews();
}

function assignResourcesConfig(config) {
  const languages = config.languages ?? {};
  const en = languages.en ?? {};
  const cz = languages.cz ?? {};
  const de = languages.de ?? {};

  document.getElementById("dbpedia_sparql_url").value = config.dbpedia_sparql_url ?? "";
  document.getElementById("en_w2v_model").value = en.w2v_model ?? "";
  document.getElementById("en_fasttext_model").value = en.fasttext_model ?? "";
  document.getElementById("cz_w2v_model").value = cz.w2v_model ?? "";
  document.getElementById("cz_fasttext_model").value = cz.fasttext_model ?? "";
  document.getElementById("cz_name_diminutives").value = cz.name_diminutives ?? "";
  document.getElementById("de_w2v_model").value = de.w2v_model ?? "";
  document.getElementById("de_fasttext_model").value = de.fasttext_model ?? "";
  renderPreviews();
}

function toYaml(value, depth = 0) {
  const indent = "  ".repeat(depth);

  if (Array.isArray(value)) {
    if (!value.length) return "[]";
    return value
      .map((item) => {
        if (item && typeof item === "object") {
          const nested = toYaml(item, depth + 1);
          return `${indent}-\n${nested}`;
        }
        return `${indent}- ${formatScalar(item)}`;
      })
      .join("\n");
  }

  if (value && typeof value === "object") {
    const entries = Object.entries(value).filter(([, entryValue]) => entryValue !== null && entryValue !== undefined);
    if (!entries.length) return "{}";
    return entries
      .map(([key, entryValue]) => {
        if (Array.isArray(entryValue)) {
          if (!entryValue.length) return `${indent}${key}: []`;
          const nested = entryValue
            .map((item) => {
              if (item && typeof item === "object") {
                return `${indent}  -\n${toYaml(item, depth + 2)}`;
              }
              return `${indent}  - ${formatScalar(item)}`;
            })
            .join("\n");
          return `${indent}${key}:\n${nested}`;
        }
        if (entryValue && typeof entryValue === "object") {
          return `${indent}${key}:\n${toYaml(entryValue, depth + 1)}`;
        }
        return `${indent}${key}: ${formatScalar(entryValue)}`;
      })
      .join("\n");
  }

  return `${indent}${formatScalar(value)}`;
}

function formatScalar(value) {
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (value === "") return "\"\"";
  const text = String(value);
  if (/^[A-Za-z0-9_./:-]+$/.test(text)) return text;
  return JSON.stringify(text);
}

function renderPreviews() {
  document.getElementById("profilePreview").textContent = JSON.stringify(collectProfile(), null, 2);
  document.getElementById("runtimePreview").textContent = toYaml(collectRuntimeConfig());
  document.getElementById("resourcesPreview").textContent = toYaml(collectResourcesConfig());
}

async function saveSection(section, path, payload) {
  try {
    const result = await postJson("/api/save", {
      section,
      path,
      payload,
    });
    setStatus(`Saved: ${result.saved}`, "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function saveProfile() {
  await saveSection(
    "profile",
    document.getElementById("profilePath").value.trim(),
    collectProfile(),
  );
}

async function saveRuntime() {
  await saveSection(
    "runtime",
    document.getElementById("runtimePath").value.trim(),
    collectRuntimeConfig(),
  );
}

async function saveResources() {
  await saveSection(
    "resources",
    document.getElementById("resourcesPath").value.trim(),
    collectResourcesConfig(),
  );
}

async function loadDefaults() {
  try {
    const response = await fetch("/api/defaults");
    const data = await response.json();
    assignProfile(data.profile);
    assignRuntimeConfig(data.runtime_config);
    assignResourcesConfig(data.resources_config);
    setStatus("Loaded defaults.", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function loadFromDisk() {
  const profilePath = document.getElementById("profilePath").value.trim();
  const runtimePath = document.getElementById("runtimePath").value.trim();
  const resourcesPath = document.getElementById("resourcesPath").value.trim();

  try {
    const response = await fetch(`/api/load?profile_path=${encodeURIComponent(profilePath)}&runtime_config_path=${encodeURIComponent(runtimePath)}&resources_config_path=${encodeURIComponent(resourcesPath)}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Failed to load files.");
    }
    if (data.profile) assignProfile(data.profile);
    if (data.runtime_config) assignRuntimeConfig(data.runtime_config);
    if (data.resources_config) assignResourcesConfig(data.resources_config);
    setStatus("Loaded files from disk.", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function bootstrap() {
  const response = await fetch("/api/defaults");
  const data = await response.json();
  state.defaults = data;
  assignProfile(data.profile);
  assignRuntimeConfig(data.runtime_config);
  assignResourcesConfig(data.resources_config);

  document.querySelectorAll("input, textarea, select").forEach((element) => {
    element.addEventListener("input", renderPreviews);
    element.addEventListener("change", renderPreviews);
  });

  if (!document.getElementById("childrenList").children.length) addChild();
  if (!document.getElementById("petsList").children.length) addPet();
  showPage("profile");
  renderPreviews();
}

window.addEventListener("load", bootstrap);
