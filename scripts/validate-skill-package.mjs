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

assert(skill?.name, "package.json must define codexSkill.name");
assert(skill?.path, "package.json must define codexSkill.path");
assert(pkg.name?.startsWith("@nick2bad4u/"), "package name must use the @nick2bad4u npm scope");
assert(pkg.publishConfig?.access === "public", "scoped package must publish with public access");
assert(
  pkg.repository?.url === "git+https://github.com/Nick2bad4u/Bundlephobia-Skill.git",
  "repository.url must exactly match the GitHub repository for npm trusted publishing",
);
assert(pkg.files?.includes(`${skill.path}/`), `package files must include ${skill.path}/`);

const skillMdPath = `${skill.path}/SKILL.md`;
const openAiMetadataPath = `${skill.path}/agents/openai.yaml`;
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
  assertFile(`${skill.path}/${smallIcon.replace(/^\.\//, "")}`),
  assertFile(`${skill.path}/${largeIcon.replace(/^\.\//, "")}`),
  assertFile(`${skill.path}/LICENSE.txt`),
  assertFile(".github/instructions/copilot-instructions.md"),
]);

console.log(`Validated ${pkg.name} skill package metadata.`);
