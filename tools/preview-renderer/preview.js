(function () {
  window.__FIGMA_PREVIEW_READY__ = false;

  function parseSceneUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("scene") || "preview_scene.json";
  }

  function applyNode(artboard, node) {
    const el = document.createElement("div");
    el.className = `node ${node.type}`;
    el.dataset.nodeId = node.id;
    el.style.left = `${node.x}px`;
    el.style.top = `${node.y}px`;
    el.style.width = `${node.width}px`;
    el.style.height = `${node.height}px`;
    if (node.opacity != null) {
      el.style.opacity = String(node.opacity);
    }

    if (node.type === "rect") {
      if (node.fill) {
        el.style.background = node.fill;
      }
      if (node.border_radius != null) {
        el.style.borderRadius = `${node.border_radius}px`;
      }
      if (node.border_width != null && node.border_color) {
        el.style.border = `${node.border_width}px solid ${node.border_color}`;
      }
    } else if (node.type === "text") {
      el.textContent = node.text || "";
      if (node.color) {
        el.style.color = node.color;
      }
      if (node.font_size != null) {
        el.style.fontSize = `${node.font_size}px`;
      }
      if (node.font_family) {
        el.style.fontFamily = node.font_family;
      }
      if (node.font_weight != null) {
        el.style.fontWeight = String(node.font_weight);
      }
      if (node.line_height != null) {
        el.style.lineHeight = `${node.line_height}px`;
      }
    } else if (node.type === "image") {
      const img = document.createElement("img");
      img.alt = "";
      if (node.image_src) {
        img.src = node.image_src;
      }
      el.appendChild(img);
    }

    artboard.appendChild(el);
    return el;
  }

  function waitForImages(artboard) {
    const images = Array.from(artboard.querySelectorAll("img"));
    if (images.length === 0) {
      return Promise.resolve();
    }
    return Promise.all(
      images.map(
        (img) =>
          new Promise((resolve) => {
            if (img.complete) {
              resolve();
              return;
            }
            img.addEventListener("load", () => resolve(), { once: true });
            img.addEventListener("error", () => resolve(), { once: true });
          }),
      ),
    );
  }

  function paintScene(scene) {
    const artboard = document.getElementById("artboard");
    artboard.style.width = `${scene.width}px`;
    artboard.style.height = `${scene.height}px`;
    artboard.style.background = scene.background || "#FFFFFF";
    artboard.replaceChildren();
    for (const node of scene.nodes || []) {
      applyNode(artboard, node);
    }
  }

  async function renderScene(scene) {
    paintScene(scene);
    const artboard = document.getElementById("artboard");
    await waitForImages(artboard);
    window.__FIGMA_PREVIEW_READY__ = true;
  }

  function renderSceneSync(scene) {
    paintScene(scene);
    window.__FIGMA_PREVIEW_READY__ = true;
  }

  function loadScene() {
    const embedded = document.getElementById("figma-preview-scene");
    if (embedded && embedded.textContent) {
      return Promise.resolve(JSON.parse(embedded.textContent));
    }
    const sceneUrl = parseSceneUrl();
    return fetch(sceneUrl).then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load scene: ${sceneUrl}`);
      }
      return response.json();
    });
  }

  async function boot() {
    const scene = await loadScene();
    await renderScene(scene);
  }

  const embedded = document.getElementById("figma-preview-scene");
  if (embedded && embedded.textContent) {
    try {
      renderSceneSync(JSON.parse(embedded.textContent));
    } catch (error) {
      console.error(error);
      window.__FIGMA_PREVIEW_READY__ = false;
      window.__FIGMA_PREVIEW_ERROR__ = String(error);
    }
  } else {
    boot().catch((error) => {
      console.error(error);
      window.__FIGMA_PREVIEW_READY__ = false;
      window.__FIGMA_PREVIEW_ERROR__ = String(error);
    });
  }
})();
