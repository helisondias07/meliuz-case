import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dashboardRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(dashboardRoot, "..");
const sourceDir = path.join(repoRoot, "outputs", "results");
const targetDir = path.join(dashboardRoot, "src", "data", "generated");
const targetFile = path.join(targetDir, "results.json");

function slugFromFileName(fileName) {
  return fileName.replace(/\.json$/i, "");
}

try {
  const files = (await readdir(sourceDir))
    .filter((file) => file.toLowerCase().endsWith(".json"))
    .sort((a, b) => a.localeCompare(b));

  const results = [];

  for (const file of files) {
    const raw = await readFile(path.join(sourceDir, file), "utf8");
    const parsed = JSON.parse(raw);
    results.push({
      id: slugFromFileName(file),
      source_file: file,
      ...parsed
    });
  }

  await mkdir(targetDir, { recursive: true });
  await writeFile(targetFile, `${JSON.stringify(results, null, 2)}\n`, "utf8");

  console.log(`Synced ${results.length} result file(s) to ${path.relative(dashboardRoot, targetFile)}.`);
} catch (error) {
  await mkdir(targetDir, { recursive: true });
  await writeFile(targetFile, "[]\n", "utf8");
  console.warn(
    `Could not sync outputs/results/*.json. The dashboard will show an empty state.\n${error.message}`
  );
}
