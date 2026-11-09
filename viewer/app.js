"use strict";

let hierarchy;
let contentIndex;
let currentPublication;
let expanded = true;

const publicationSelect = document.getElementById("publicationSelect");
const searchInput = document.getElementById("searchInput");
const tree = document.getElementById("tree");
const content = document.getElementById("content");
const partSearchResults = document.getElementById("partSearchResults");
let searchIndexPromise;

async function startApp() {
  try {
    const [hierarchyResponse, indexResponse] = await Promise.all([
      fetch("data/hierarchy.json"),
      fetch("data/content-index.json")
    ]);

    if (!hierarchyResponse.ok || !indexResponse.ok) {
      throw new Error("Could not load the manual data.");
    }

    hierarchy = await hierarchyResponse.json();
    contentIndex = await indexResponse.json();

    hierarchy.publications.forEach(pub => {
      const option = document.createElement("option");
      option.value = pub.id;
      option.textContent = pub.title;
      publicationSelect.appendChild(option);
    });

    publicationSelect.value = "X001724";
    loadPublication();

    history.replaceState({
      workshopManual: true,
      publicationId: currentPublication.id,
      home: true
    }, "", window.location.href);

  } catch (error) {
    content.textContent = "Unable to load manual: " + error.message;
  }
}

function loadPublication() {
  currentPublication = hierarchy.publications.find(
    pub => pub.id === publicationSelect.value
  );

  if (currentPublication) {
    searchInput.value = "";
    renderTree();
  }
}

startApp();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js")
      .catch(error => console.error("Offline support registration failed:", error));
  });
}


// Download all catalogue and procedure data for offline use.
const offlineDownloadButton = document.getElementById("offlineDownloadButton");
const offlineDownloadProgress = document.getElementById("offlineDownloadProgress");
const offlineDownloadStatus = document.getElementById("offlineDownloadStatus");

offlineDownloadButton.addEventListener("click", downloadOfflineData);

async function downloadOfflineData() {
  offlineDownloadButton.disabled = true;
  offlineDownloadProgress.hidden = false;
  offlineDownloadProgress.value = 0;
  offlineDownloadStatus.textContent = "Preparing offline download...";

  try {
    if (!("serviceWorker" in navigator) || !("caches" in window)) {
      throw new Error("Offline storage is not supported by this browser.");
    }

    const registration = await navigator.serviceWorker.ready;
    if (!registration.active) {
      throw new Error("Offline service worker is not active. Reload the page and try again.");
    }

    const response = await fetch("data/offline-files.json");
    if (!response.ok) {
      throw new Error("Could not load the offline file list.");
    }

    const files = await response.json();
    const cache = await caches.open("workshop-manual-mobile-v1");
    let completed = 0;
    let failed = [];

    offlineDownloadStatus.textContent =
      "Downloading " + files.length + " manual files...";

    const batchSize = 10;

    for (let start = 0; start < files.length; start += batchSize) {
      const batch = files.slice(start, start + batchSize);

      const results = await Promise.all(batch.map(async file => {
        try {
          const url = new URL(file, document.baseURI);
          const cached = await cache.match(url);

          if (!cached) {
            const result = await fetch(url);
            if (!result.ok) {
              throw new Error("HTTP " + result.status);
            }
            await cache.put(url, result);
          }
        } catch (error) {
          failed.push(file + ": " + error.message);
        }

        completed++;
      }));

      offlineDownloadProgress.value =
        Math.round((completed / files.length) * 100);

      offlineDownloadStatus.textContent =
        "Downloaded " + completed + " of " + files.length +
        " files (" + offlineDownloadProgress.value + "%)";
    }

    if (failed.length) {
      offlineDownloadStatus.textContent =
        "Download finished with " + failed.length +
        " errors. Check your connection and try again.";
      console.error("Offline download failures:", failed);
    } else {
      offlineDownloadStatus.textContent =
        "Offline download complete. All " + files.length +
        " catalogue and procedure files are stored on this device.";
    }

  } catch (error) {
    offlineDownloadStatus.textContent = "Offline download failed: " + error.message;
    console.error(error);
  } finally {
    offlineDownloadButton.disabled = false;
  }
}

// Build the publication navigation tree.
function nodeMatches(node, query) {
  if (!query) return true;

  if (node.title.toLowerCase().includes(query)) return true;

  return (node.children || []).some(child =>
    nodeMatches(child, query)
  );
}

function renderTree() {
  tree.replaceChildren();

  const query = searchInput.value.trim().toLowerCase();

  function addNode(node, parent) {
    if (!nodeMatches(node, query)) return;

    const hasChildren = node.children && node.children.length > 0;
    const wrapper = document.createElement(
      hasChildren ? "details" : "div"
    );

    wrapper.className = "tree-node";

    if (hasChildren) {
      wrapper.open = query ? true : expanded;

      const summary = document.createElement("summary");
      summary.textContent = node.title;
      summary.title = node.type + " — " + node.id;
      wrapper.appendChild(summary);

      summary.addEventListener("click", () => {
        if (node.type !== "map" && node.type !== "bookmap") {
          showTopic(node);
        }
      });

      const children = document.createElement("div");
      children.className = "tree-children";

      node.children.forEach(child => addNode(child, children));
      wrapper.appendChild(children);

    } else {
      const button = document.createElement("button");
      button.className = "tree-leaf";
      button.textContent = node.title;
      button.title = node.type + " — " + node.id;
      button.addEventListener("click", () => showTopic(node));
      wrapper.appendChild(button);
    }

    parent.appendChild(wrapper);
  }

  currentPublication.children.forEach(node => addNode(node, tree));
}

publicationSelect.addEventListener("change", () => {
  loadPublication();

  history.pushState({
    workshopManual: true,
    publicationId: currentPublication.id,
    home: true
  }, "", window.location.href);

  content.replaceChildren();
});
async function renderPartSearchResults(query) {
  partSearchResults.replaceChildren();

  if (query.length < 2 || !currentPublication) return;

  try {
    if (!searchIndexPromise) {
      searchIndexPromise = fetch("data/search-index.json")
        .then(response => {
          if (!response.ok) {
            throw new Error("Could not load the parts search index.");
          }
          return response.json();
        });
    }

    const searchIndex = await searchIndexPromise;

    if (query !== searchInput.value.trim().toLowerCase()) return;

    const matches = searchIndex.filter(item =>
      item.publication_id === currentPublication.id &&
      (
        item.part_number.toLowerCase().includes(query) ||
        item.description.toLowerCase().includes(query) ||
        item.topic_title.toLowerCase().includes(query) ||
        item.section.toLowerCase().includes(query)
      )
    );

    if (matches.length === 0) {
      partSearchResults.textContent = "No matching parts found.";
      return;
    }

    const heading = document.createElement("strong");
    heading.textContent =
      `Parts (${matches.length})`;
    partSearchResults.appendChild(heading);

    matches.slice(0, 40).forEach(item => {
      const button = document.createElement("button");
      button.className = "part-search-result";
      button.type = "button";

      const number = document.createElement("strong");
      number.textContent = item.part_number;

      const description = document.createElement("span");
      description.textContent = item.description;

      const topic = document.createElement("small");
      topic.textContent = item.topic_title;

      button.append(number, description, topic);

      button.addEventListener("click", () => {
        showTopic({
          id: item.topic_id,
          title: item.topic_title,
          type: "topic"
        });
      });

      partSearchResults.appendChild(button);
    });

    if (matches.length > 40) {
      const note = document.createElement("small");
      note.textContent = `Showing first 40 of ${matches.length} matches.`;
      partSearchResults.appendChild(note);
    }

  } catch (error) {
    partSearchResults.textContent = error.message;
    searchIndexPromise = null;
  }
}

searchInput.addEventListener("input", () => {
  const query = searchInput.value.trim().toLowerCase();
  renderTree();
  renderPartSearchResults(query);
});

document.getElementById("expandButton").addEventListener("click", () => {
  expanded = !expanded;
  document.getElementById("expandButton").textContent =
    expanded ? "Collapse all" : "Expand all";
  renderTree();
});

document.getElementById("menuButton").addEventListener("click", () => {
  document.getElementById("navigation").classList.toggle("open");
});

// Display selected topic or procedure information.
async function showTopic(node, options = {}) {
  if (!options.fromHistory) {
    history.pushState({
      workshopManual: true,
      publicationId: currentPublication.id,
      id: node.id,
      title: node.title,
      type: node.type
    }, "", window.location.href);
  }

  content.replaceChildren();

  const heading = document.createElement("h2");
  heading.textContent = node.title;

  const details = document.createElement("div");
  details.className = "content-card";
  details.appendChild(heading);

  const record = contentIndex.records.find(r =>
    r.publication_id === currentPublication.id &&
    r.id === node.id
  );

  if (!record) {
    details.append("No matching content record was found.");
    content.appendChild(details);
    return;
  }

  const info = document.createElement("p");
  info.className = "topic-info";
  info.textContent =
    `${record.type.toUpperCase()} · ${record.id} · ${record.status}`;
  details.appendChild(info);
  content.appendChild(details);

  // Load catalogue data when this topic has a parts list.
  const catalogueUrl =
    `data/catalogues/${currentPublication.id}/${node.id}.json`;

  try {
    const response = await fetch(catalogueUrl);
    if (response.ok) {
      renderCatalogue(await response.json());
    }
  } catch (error) {
    console.error("Catalogue loading error:", error);
  }

  // Load extracted workshop procedure data when available.
  const procedureUrl =
    `data/procedures/${currentPublication.id}/${node.id}.json`;

  try {
    const response = await fetch(procedureUrl);
    if (response.ok) {
      renderProcedure(await response.json());
    }
  } catch (error) {
    console.error("Procedure loading error:", error);
  }
}

window.addEventListener("popstate", event => {
  const state = event.state;

  if (!state || !state.workshopManual) return;

  publicationSelect.value = state.publicationId;
  loadPublication();

  if (state.home) {
    content.replaceChildren();
    return;
  }

  showTopic({
    id: state.id,
    title: state.title,
    type: state.type
  }, { fromHistory: true });
});

function renderCatalogue(catalogue) {
  const section = document.createElement("section");
  section.className = "content-card catalogue";

  const heading = document.createElement("h3");
  heading.textContent = "Parts list";
  section.appendChild(heading);

  if (catalogue.views && catalogue.views.length) {
    const views = document.createElement("p");
    views.textContent = "Views: " +
      catalogue.views.map(v => v.description).join(", ");
    section.appendChild(views);
  }

  if (catalogue.illustrations && catalogue.illustrations.length) {
    const note = document.createElement("p");
    note.className = "illustration-placeholder";
    note.textContent =
      `${catalogue.illustrations.length} illustration reference(s) available.`;
    section.appendChild(note);
  } else {
    const note = document.createElement("p");
    note.className = "illustration-placeholder";
    note.textContent = "Illustration display area — images can be added later.";
    section.appendChild(note);
  }

  (catalogue.tables || []).forEach(tableData => {
    const tableScroll = document.createElement("div");
    tableScroll.className = "table-scroll";
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");

    tableData.headers.forEach(label => {
      const th = document.createElement("th");
      th.textContent = label;
      headerRow.appendChild(th);
    });

    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");

    tableData.rows.forEach(row => {
      const tr = document.createElement("tr");

      tableData.headers.forEach(label => {
        const td = document.createElement("td");
        td.textContent = row[label] || "";
        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    tableScroll.appendChild(table);
    section.appendChild(tableScroll);
  });

  content.appendChild(section);
}

// Display extracted workshop procedure steps and warnings.
function renderProcedure(procedure) {
  const section = document.createElement("section");
  section.className = "content-card procedure";

  const heading = document.createElement("h3");
  heading.textContent = "Procedure";
  section.appendChild(heading);

  const steps = document.createElement("ol");
  steps.className = "procedure-steps";

  function addContent(item, parent) {
    if (item.type === "text") {
      parent.appendChild(document.createTextNode(item.text || ""));
      return;
    }

    if (item.type === "warning") {
      const warning = document.createElement("div");
      warning.className = "procedure-warning";

      const label = document.createElement("strong");
      label.textContent =
        `${item.symbol || "⚠"} ${item.heading || "WARNING"}`;

      const message = document.createElement("p");
      message.textContent = item.text || "";

      warning.append(label, message);
      parent.appendChild(warning);
      return;
    }

    if (item.type === "included_procedure") {
      const label = item.label || item.target_title || "Related procedure";

      if (!item.target_id) {
        const reference = document.createElement("p");
        reference.className = "included-procedure";
        reference.textContent = "Related procedure: " + label;
        parent.appendChild(reference);
        return;
      }

      const related = document.createElement("button");
      related.className = "included-procedure";
      related.type = "button";
      related.style.marginTop = "10px";
      related.textContent = "Related procedure: " + label;
      related.addEventListener("click", () => {
        showTopic({
          id: item.target_id,
          title: item.target_title || label,
          type: "task"
        });
      });
      parent.appendChild(related);
      return;
    }

    if (item.type === "element") {
      const element = document.createElement("div");
      (item.children || []).forEach(child => addContent(child, element));
      parent.appendChild(element);
    }
  }

  (procedure.steps || []).forEach(step => {
    const li = document.createElement("li");

    (step.content || []).forEach(item => addContent(item, li));

    steps.appendChild(li);
  });

  section.appendChild(steps);
  content.appendChild(section);
}
