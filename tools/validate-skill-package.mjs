import { access, readFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const pkg = JSON.parse(await readFile(path.join(root, "package.json"), "utf8"));
const skill = pkg.codexSkill;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function assertFile(relativePath) {
  await access(path.join(root, relativePath));
}

function skillRelative(relativePath) {
  return skill.path === "." ? relativePath : `${skill.path}/${relativePath}`;
}

function linesOf(text) {
  return text.replaceAll("\r\n", "\n").replaceAll("\r", "\n").split("\n");
}

function stripMatchingQuotes(value) {
  const first = value.at(0);
  const last = value.at(-1);
  if ((first === "\"" || first === "'") && first === last) {
    return value.slice(1, -1);
  }
  return value;
}

function stripCurrentDirectoryPrefix(value) {
  return value.startsWith("./") ? value.slice(2) : value;
}

function frontmatterValue(markdown, key) {
  const lines = linesOf(markdown);
  if (lines[0] !== "---") {
    return undefined;
  }

  for (const line of lines.slice(1)) {
    if (line === "---") {
      return undefined;
    }

    const separatorIndex = line.indexOf(":");
    if (separatorIndex === -1) {
      continue;
    }

    if (line.slice(0, separatorIndex).trim() !== key) {
      continue;
    }

    return stripMatchingQuotes(line.slice(separatorIndex + 1).trim());
  }

  return undefined;
}

function yamlStringValue(yaml, key) {
  const prefix = `${key}:`;
  for (const line of linesOf(yaml)) {
    const trimmed = line.trim();
    if (!trimmed.startsWith(prefix)) {
      continue;
    }

    return stripMatchingQuotes(trimmed.slice(prefix.length).trim());
  }

  return undefined;
}

assert(skill?.name, "package.json must define codexSkill.name");
assert(skill?.path, "package.json must define codexSkill.path");
assert(pkg.name === "bundle-size-analysis-skill", "package name must be bundle-size-analysis-skill");
assert(
  pkg.repository?.url === "git+https://github.com/Nick2bad4u/Bundlephobia-Skill.git",
  "repository.url must exactly match the GitHub repository for npm trusted publishing",
);
assert(skill.path === ".", "codexSkill.path must point at the repository root");
for (const requiredFile of ["SKILL.md", "LICENSE.txt", "agents/", "assets/", "scripts/", "README.md", "CHANGELOG.md", "SECURITY.md"]) {
  assert(pkg.files?.includes(requiredFile), `package files must include ${requiredFile}`);
}
for (const forbiddenFile of [".github/skills/", ".github/instructions/", "dist/", "tools/"]) {
  assert(!pkg.files?.some((entry) => entry.startsWith(forbiddenFile)), `package files must not include ${forbiddenFile}`);
}

const skillMdPath = skillRelative("SKILL.md");
const openAiMetadataPath = skillRelative("agents/openai.yaml");
const skillMd = await readFile(path.join(root, skillMdPath), "utf8");
const openAiMetadata = await readFile(path.join(root, openAiMetadataPath), "utf8");

assert(skillMd.startsWith("---"), "SKILL.md must start with YAML frontmatter");
assert(frontmatterValue(skillMd, "name") === skill.name, "SKILL.md frontmatter name must match package codexSkill.name");
assert(frontmatterValue(skillMd, "description"), "SKILL.md frontmatter must include description");
assert(skillMd.includes("\nmetadata:\n") || skillMd.includes("\r\nmetadata:\r\n"), "SKILL.md frontmatter must include metadata block");

const smallIcon = yamlStringValue(openAiMetadata, "icon_small");
const largeIcon = yamlStringValue(openAiMetadata, "icon_large");

assert(linesOf(openAiMetadata).some((line) => line.trim() === "interface:"), "agents/openai.yaml must include interface metadata");
assert(smallIcon, "agents/openai.yaml must define icon_small");
assert(largeIcon, "agents/openai.yaml must define icon_large");

await Promise.all([
  assertFile(skillRelative(stripCurrentDirectoryPrefix(smallIcon))),
  assertFile(skillRelative(stripCurrentDirectoryPrefix(largeIcon))),
  assertFile(skillRelative("LICENSE.txt")),
]);

console.log(`Validated ${pkg.name} skill package metadata.`);
