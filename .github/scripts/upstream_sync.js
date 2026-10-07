// Reports new home-assistant/core commits that touch the upstream Discogs
// integration, so changes there can be reviewed and ported by hand.
//
// Run by .github/workflows/upstream-sync-check.yml via actions/github-script.
// It never commits or pushes: the "last seen" position is stored as a hidden
// marker in the tracking issue itself, so the workflow only needs
// `issues: write` and works with branch rulesets that block direct pushes.
//
// Flow:
//   1. Find the newest marker across all `upstream-sync` issues (open or
//      closed). With no marker yet, start from BASELINE_DATE.
//   2. List upstream commits on `dev` touching UPSTREAM_PATH since then.
//   3. If any, comment on the open tracking issue (or open a new one) with
//      each commit's title, link, and the diff for files under UPSTREAM_PATH,
//      plus an updated marker.
//
// Close the issue once you've reviewed/ported the changes; the next upstream
// change opens a fresh one, picking up from the marker in the closed issue.

"use strict";

const UPSTREAM = { owner: "home-assistant", repo: "core", branch: "dev" };
const LABEL = "upstream-sync";
const MARKER_RE =
  /<!-- upstream-sync:last-seen sha=([0-9a-f]{40}) date=(\S+) -->/g;
const MAX_COMMITS = 100;
const MAX_PATCH_CHARS = 4000;
const MAX_BODY_CHARS = 60000;

function marker(sha, date) {
  return `<!-- upstream-sync:last-seen sha=${sha} date=${date} -->`;
}

// Returns the last marker found in `text`, or null.
function lastMarker(text) {
  let found = null;
  for (const m of (text || "").matchAll(MARKER_RE)) {
    found = { sha: m[1], date: m[2] };
  }
  return found;
}

async function findState({ github, owner, repo }) {
  const issues = await github.paginate(github.rest.issues.listForRepo, {
    owner,
    repo,
    labels: LABEL,
    state: "all",
    sort: "created",
    direction: "desc",
    per_page: 100,
  });
  const open = issues.find((i) => i.state === "open" && !i.pull_request);

  let best = null;
  for (const issue of issues) {
    if (issue.pull_request) continue;
    const comments = await github.paginate(github.rest.issues.listComments, {
      owner,
      repo,
      issue_number: issue.number,
      per_page: 100,
    });
    for (const text of [issue.body, ...comments.map((c) => c.body)]) {
      const m = lastMarker(text);
      if (m && (!best || Date.parse(m.date) >= Date.parse(best.date))) {
        best = m;
      }
    }
  }
  return { open, lastSeen: best };
}

function truncate(text, max) {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}\n… (truncated, see the commit for the full diff)`;
}

async function describeCommit({ github, sha, path }) {
  const { data } = await github.rest.repos.getCommit({
    owner: UPSTREAM.owner,
    repo: UPSTREAM.repo,
    ref: sha,
  });
  const title = data.commit.message.split("\n")[0];
  const date = data.commit.committer.date;
  const files = (data.files || []).filter((f) =>
    f.filename.startsWith(`${path}/`),
  );
  let out = `### [\`${sha.slice(0, 10)}\`](${data.html_url}) ${title}\n`;
  out += `Committed ${date}\n\n`;
  for (const f of files) {
    const rel = f.filename.slice(path.length + 1);
    out += `- \`${rel}\` (${f.status}, +${f.additions}/-${f.deletions})\n`;
  }
  for (const f of files) {
    if (!f.patch) continue;
    const rel = f.filename.slice(path.length + 1);
    out += `\n<details><summary><code>${rel}</code></summary>\n\n`;
    out += "```diff\n" + truncate(f.patch, MAX_PATCH_CHARS) + "\n```\n</details>\n";
  }
  return out + "\n";
}

async function ensureLabel({ github, owner, repo }) {
  try {
    await github.rest.issues.getLabel({ owner, repo, name: LABEL });
  } catch (err) {
    if (err.status !== 404) throw err;
    await github.rest.issues.createLabel({
      owner,
      repo,
      name: LABEL,
      color: "0e8a16",
      description: "Upstream home-assistant/core changes to review",
    });
  }
}

module.exports = async ({ github, context, core }) => {
  const { owner, repo } = context.repo;
  const path = process.env.UPSTREAM_PATH;
  const baselineDate = process.env.BASELINE_DATE;
  if (!path || !baselineDate) {
    core.setFailed("UPSTREAM_PATH and BASELINE_DATE must be set");
    return;
  }

  const { open, lastSeen } = await findState({ github, owner, repo });
  const since = lastSeen ? lastSeen.date : baselineDate;
  core.info(
    `Checking ${UPSTREAM.owner}/${UPSTREAM.repo}@${UPSTREAM.branch}:${path} since ${since}` +
      (lastSeen ? ` (last seen ${lastSeen.sha.slice(0, 10)})` : " (baseline)"),
  );

  const listed = await github.paginate(github.rest.repos.listCommits, {
    owner: UPSTREAM.owner,
    repo: UPSTREAM.repo,
    sha: UPSTREAM.branch,
    path,
    since,
    per_page: 100,
  });
  // `since` is inclusive, so the last-seen commit itself comes back again.
  const fresh = listed
    .filter((c) => !lastSeen || c.sha !== lastSeen.sha)
    .slice(0, MAX_COMMITS)
    .reverse(); // oldest first

  if (fresh.length === 0) {
    core.info("No new upstream changes.");
    core.setOutput("changed", "false");
    return;
  }

  const newest = fresh[fresh.length - 1];
  const newestDate = newest.commit.committer.date;
  let body =
    `**${fresh.length}** new upstream commit(s) touching ` +
    `[\`${path}\`](https://github.com/${UPSTREAM.owner}/${UPSTREAM.repo}/tree/${UPSTREAM.branch}/${path}) ` +
    `since ${since}.\n\n` +
    "Nothing is merged automatically. Review each change and port what " +
    "applies by hand, then close this issue.\n\n";
  for (const c of fresh) {
    body += await describeCommit({ github, sha: c.sha, path });
  }
  body = truncate(body, MAX_BODY_CHARS - 200) + "\n" + marker(newest.sha, newestDate);

  await ensureLabel({ github, owner, repo });
  if (open) {
    await github.rest.issues.createComment({
      owner,
      repo,
      issue_number: open.number,
      body,
    });
    core.info(`Commented on #${open.number}`);
  } else {
    const { data } = await github.rest.issues.create({
      owner,
      repo,
      title: `Upstream ${path.split("/").pop()} changed in ${UPSTREAM.owner}/${UPSTREAM.repo}`,
      body,
      labels: [LABEL],
    });
    core.info(`Opened #${data.number}`);
  }
  core.setOutput("changed", "true");
};

// Exported for tests.
module.exports.lastMarker = lastMarker;
module.exports.marker = marker;
