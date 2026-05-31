// figma-css-inspect plugin
// Экспортирует CSS из Inspect-панели для выбранного фрейма в формат v1 dump.

figma.showUI(__html__, { width: 420, height: 260, title: "CSS Inspect Export" });

async function collectCss(node, result) {
  let css = {};
  try {
    css = await node.getCSSAsync();
  } catch (_) {
    // нода не поддерживает getCSSAsync (например, group без заливки)
  }

  if (Object.keys(css).length > 0) {
    result[node.id] = { name: node.name, css };
  }

  if ("children" in node) {
    for (const child of node.children) {
      await collectCss(child, result);
    }
  }
}

figma.ui.onmessage = async (msg) => {
  if (msg.type !== "export") return;

  const selection = figma.currentPage.selection;
  if (selection.length === 0) {
    figma.ui.postMessage({ type: "error", text: "Выдели фрейм в Figma и нажми Export." });
    return;
  }

  figma.ui.postMessage({ type: "progress", text: "Читаю CSS..." });

  const nodes = {};
  for (const node of selection) {
    await collectCss(node, nodes);
  }

  const frameNames = selection.map((n) => n.name).join(", ");
  const dump = {
    version: 1,
    fileKey: figma.fileKey || "",
    exportedAt: new Date().toISOString(),
    nodes,
  };

  figma.ui.postMessage({
    type: "done",
    json: JSON.stringify(dump, null, 2),
    nodeCount: Object.keys(nodes).length,
    frameNames,
  });
};
