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
assert(new RegExp(`^name:\\s*"?${skill.name}"?\\s*$`, "m").test(skillMd), "SKILL.md frontmatter name must match package codexSkill.name");
assert(/^description:\s+/m.test(skillMd), "SKILL.md frontmatter must include description");
assert(/^metadata:\s*$/m.test(skillMd), "SKILL.md frontmatter must include metadata block");

const smallIcon = openAiMetadata.match(/^\s*icon_small:\s*["']?(.+?)["']?\s*$/m)?.[1];
const largeIcon = openAiMetadata.match(/^\s*icon_large:\s*["']?(.+?)["']?\s*$/m)?.[1];

assert(/^interface:\s*$/m.test(openAiMetadata), "agents/openai.yaml must include interface metadata");
assert(smallIcon, "agents/openai.yaml must define icon_small");
assert(largeIcon, "agents/openai.yaml must define icon_large");

await Promise.all([
  assertFile(skillRelative(smallIcon.replace(/^\.\//, ""))),
  assertFile(skillRelative(largeIcon.replace(/^\.\//, ""))),
  assertFile(skillRelative("LICENSE.txt")),
]);

console.log(`Validated ${pkg.name} skill package metadata.`);
