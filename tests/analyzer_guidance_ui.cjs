// Renders OperationalGuidancePanel (the real component) with guidance JSON produced by the real backend and prints a JSON report.
// Usage: node tests/analyzer_guidance_ui.cjs <input.json>   (input: {"cases": {name: guidance-or-null}})
const fs = require("fs");
const path = require("path");
const Module = require("module");
const dash = path.resolve(__dirname, "..", "clients", "dashboard");
const req = Module.createRequire(path.join(dash, "package.json"));
const ts = req("typescript");
const React = req("react");
const { renderToStaticMarkup } = req("react-dom/server");

const file = path.join(dash, "src", "components", "OperationalGuidancePanel.tsx");
const out = ts.transpileModule(fs.readFileSync(file, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2019, esModuleInterop: true },
}).outputText;
const mod = new Module(file, null);
mod.filename = file;
mod.paths = Module._nodeModulePaths(path.dirname(file));
mod._compile(out, file);  // compiles repo-owned source with normal module resolution (no dynamic function construction)
const Panel = mod.exports.default;

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const report = {};
for (const [name, guidance] of Object.entries(input.cases)) {
  const html = renderToStaticMarkup(React.createElement(Panel, { guidance, isEn: true }));
  const rows = {};
  for (const m of html.matchAll(/data-testid="(g-[a-z]+)" data-status="([a-z_]+)"/g)) rows[m[1]] = m[2];
  report[name] = {
    rendered: html.length > 0,
    rows,
    destructiveWarning: html.includes('data-testid="destructive-warning"'),
    pendingBanner: html.includes("pending human review"),
    unverifiedNotice: html.includes("Unconfirmed"),
    notStatedText: (html.match(/No source-backed information/g) || []).length,
    html,
  };
}
process.stdout.write(JSON.stringify(report));
