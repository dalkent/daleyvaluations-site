# Deploy Guide - daleyvaluations.com

End-to-end walkthrough from "site folder on my computer" to "live at daleyvaluations.com." Allow 30-45 minutes the first time, then about 30 seconds per future change.

---

## 0. Prerequisites

You need three accounts, all free:

1. **GitHub** - github.com. Sign up if you haven't already. Use the email you check.
2. **Cloudflare** - dash.cloudflare.com. You should already have one because you registered the domain there.
3. **Git on your machine** - already installed if you've used VS Code or any modern dev tool. To check, open a terminal and run `git --version`. If it errors, install from git-scm.com.

---

## 1. Create the GitHub repo (5 minutes)

1. Go to github.com.
2. Top right, click the **+** icon, then **New repository**.
3. Repository name: `daleyvaluations-site`
4. Description: `Source for daleyvaluations.com - equity research site by Neil Daley, PhD, CFA.`
5. Visibility: **Public**
6. Initialise: **leave all checkboxes unchecked**. Don't add a README, .gitignore, or licence - we already have those files locally.
7. Click **Create repository**.

GitHub will show you a page with setup instructions. Leave that tab open. You'll need the URL it shows in the next step.

---

## 2. Push your local folder to GitHub (10 minutes)

Open a terminal. Navigate to the site folder:

```
cd "C:\Users\Neil\My Drive\Daley's Brain\Projects\eToro & Investing\Drafts\daleyvaluations-site"
```

If you've never used Git before, set your name and email globally first:

```
git config --global user.name "Neil Daley"
git config --global user.email "ndaley1313@gmail.com"
```

Then initialise the repo, add the files, commit, and push:

```
git init
git add .
git commit -m "Initial commit: methodology page"
git branch -M main
git remote add origin https://github.com/dalkent/daleyvaluations-site.git
git push -u origin main
```

Replace `<your-username>` with your actual GitHub username.

The first `git push` will ask you to authenticate. The modern way is via a Personal Access Token, not your password:

1. On GitHub, top right → **Settings** → **Developer settings** (very bottom of left sidebar) → **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**.
2. Note: `daleyvaluations-site push access`
3. Expiration: 90 days is fine for a first try; you can always regenerate.
4. Scopes: tick **repo** only.
5. Generate. Copy the token (starts with `ghp_`).
6. When `git push` asks for password, paste the token instead of your actual password.

If the push succeeds, refresh the GitHub repo page. You should see all six files: `index.html`, `README.md`, `.gitignore`, `LICENSE`, `robots.txt`, `CNAME`.

---

## 3. Connect Cloudflare Pages to the repo (10 minutes)

1. Log in to dash.cloudflare.com.
2. Left sidebar: **Workers & Pages**.
3. Top right: **Create application** → **Pages** tab → **Connect to Git**.
4. Authorise Cloudflare to access your GitHub if prompted. You can grant access to all repos or just `daleyvaluations-site` - pick whichever feels right.
5. Select the `daleyvaluations-site` repo. Click **Begin setup**.
6. Project name: `daleyvaluations` (this becomes part of the temporary preview URL: `daleyvaluations.pages.dev`).
7. Production branch: `main`.
8. Build settings:
   - Framework preset: **None**
   - Build command: leave **blank**
   - Build output directory: `/` (or leave blank - same thing)
9. Environment variables: **none**.
10. Click **Save and Deploy**.

Wait about 30 seconds. The first deploy is fast because there's no build step. Cloudflare will give you a `https://daleyvaluations.pages.dev` URL. Open it. The methodology page should appear, complete with the green/yellow/red signal badges and the assumptions table.

If it works at the `.pages.dev` URL, the hard part is done.

---

## 4. Point your custom domain at the site (5 minutes)

1. Still in Cloudflare Pages, in your project, click the **Custom domains** tab.
2. Click **Set up a custom domain**.
3. Enter `daleyvaluations.com` (the apex domain, no `www`). Click **Continue**.
4. Cloudflare will detect that you registered the domain with them and offer to add the CNAME record automatically. Click **Activate domain**.
5. Repeat for `www.daleyvaluations.com` if you want both. Cloudflare can be set to redirect one to the other. The convention is apex (`daleyvaluations.com`) as canonical, with `www` redirecting to it.

DNS propagation is usually instant when both registrar and host are Cloudflare. You can also test at:

```
https://daleyvaluations.com
```

within a minute or two. SSL certificate is auto-issued, so HTTPS works from the start.

---

## 5. Verify the deploy

Open `https://daleyvaluations.com` in a private/incognito window (to bypass any cached redirects). You should see:

- The methodology page rendering correctly
- HTTPS green padlock in the address bar
- Page title `Methodology | Daley Valuations`
- Signal badges in the right colours
- Footer showing "Last reviewed: 29 April 2026"

Also check `https://daleyvaluations.com/robots.txt` opens correctly. That confirms static assets serve as expected.

---

## 6. Future changes

Once everything above is set up, deploying a change is three commands:

```
cd "C:\Users\Neil\My Drive\Daley's Brain\Projects\eToro & Investing\Drafts\daleyvaluations-site"
git add .
git commit -m "Update methodology page assumptions"
git push
```

Cloudflare detects the push within seconds, rebuilds, and deploys. Total time from save to live: usually under a minute.

---

## Troubleshooting

**`git push` fails with "remote: Repository not found".** Your GitHub username in the `git remote add origin` line is wrong. Run `git remote -v` to see what it's set to. Fix with `git remote set-url origin https://github.com/<correct-username>/daleyvaluations-site.git`.

**`git push` fails with "Authentication failed".** You're using your GitHub password instead of a Personal Access Token. Regenerate the token (Step 2) and use that.

**Cloudflare deploy fails.** Most likely cause: Cloudflare can't see the `index.html` because the build output directory is wrong. Check Pages → your project → Settings → Build & deployments. The output directory should be empty or `/`. Re-trigger a deploy from the Deployments tab.

**Domain shows "Page not found" but `.pages.dev` works.** DNS hasn't propagated yet. Wait 5 minutes and try again in a fresh incognito window. If still broken after 30 minutes, check Cloudflare DNS for the CNAME record pointing `daleyvaluations.com` at `daleyvaluations.pages.dev`.

**SSL error on first visit.** Cloudflare's certificate takes a minute or two to issue. Wait, then refresh. If it persists after 15 minutes, in the Cloudflare dashboard go to your domain → SSL/TLS → Edge Certificates and check that "Always Use HTTPS" is on and the Universal SSL certificate shows "Active".

**Page renders but the signal badges have no colour.** Probably a typo in the HTML. Open the file in your browser locally first. If it works locally but not deployed, you've pushed an old version - check `git log` and `git status`.

---

## What you do not have to do

You do not have to:
- Set up a build pipeline. There isn't one.
- Configure DNS records manually. Cloudflare handles it.
- Buy SSL certificates. They're free and auto-issued.
- Pay for hosting. The free Cloudflare Pages tier is far more than this site will ever need.
- Maintain a server. There is no server, only static files on Cloudflare's CDN.

---

## What's next

Stage 2 is the live valuation tracker. That requires the data pipeline that feeds JSON files from `etoro_master.json` into the site. The architecture for that is:

1. The existing `ftse-tracker-weekly` scheduled task (Mon 5pm) regenerates the JSON.
2. A new Python script in this repo reads the JSON and generates `tracker.html` (or rebuilds `index.html` as the tracker page, with methodology moving to `/methodology.html`).
3. The script commits the new HTML and pushes. Cloudflare auto-deploys.

That work happens when Stage 1 has been live for two to four weeks and you've sat with it. For now, ship Stage 1.
