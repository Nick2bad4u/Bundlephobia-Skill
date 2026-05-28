import { cp, mkdir, readdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const sourcePkg = JSON.parse(await readFile(path.join(root, "package.json"), "utf8"));
const skill = sourcePkg.codexSkill;
const sourceSkillDir = path.join(root, skill.path);
const outDir = path.join(root, "dist", "npm");

async function exists(relativePath) {
  try {
    await stat(path.join(outDir, relativePath));
    return true;
  } catch {
    return false;
  }
}

await rm(outDir, { force: true, recursive: true });
await mkdir(outDir, { recursive: true });

for (const entry of await readdir(sourceSkillDir)) {
  await cp(path.join(sourceSkillDir, entry), path.join(outDir, entry), { recursive: true });
}

for (const doc of ["README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md"]) {
  await cp(path.join(root, doc), path.join(outDir, doc));
}

const files = [];
for (const candidate of [
  "SKILL.md",
  "LICENSE.txt",
  "agents/",
  "assets/",
  "references/",
  "scripts/",
  "README.md",
  "CHANGELOG.md",
  "CONTRIBUTING.md",
  "SECURITY.md",
]) {
  if (await exists(candidate.replace(/\/$/, ""))) {
    files.push(candidate);
  }
}

const publishPkg = {
  name: sourcePkg.name,
  version: sourcePkg.version,
  description: sourcePkg.description,
  license: sourcePkg.license,
  type: sourcePkg.type,
  repository: sourcePkg.repository,
  bugs: sourcePkg.bugs,
  homepage: sourcePkg.homepage,
  keywords: sourcePkg.keywords,
  files,
  publishConfig: sourcePkg.publishConfig,
  engines: sourcePkg.engines,
  codexSkill: {
    name: skill.name,
    path: ".",
  },
};

await writeFile(path.join(outDir, "package.json"), `${JSON.stringify(publishPkg, null, 2)}\n`);

console.log(`Built npm skill package at ${path.relative(root, outDir)}`);
