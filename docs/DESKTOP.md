# The desktop app (Mac .dmg and Windows .exe)

The desktop app is a native window that opens your hosted site
(`https://znnajiofor.pythonanywhere.com`). Because it just shows the live site:

- **New homilies are always included** — it reads the same database your iPad does.
- **Your iPad keeps working** — all your devices share the one server.
- Updating the web app (git pull + Reload) updates the desktop app too; no rebuild.

It needs an internet connection, like the iPad app.

## How the installers are built (no build on your mac)

A GitHub Actions workflow (`.github/workflows/build-desktop.yml`) builds the
installers in the cloud — a Mac runner makes the `.dmg`, a Windows runner makes
the `.exe` — and attaches them to a GitHub **Release**.

**To build (or rebuild) the installers:**

1. Make sure the code is pushed to GitHub.
2. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
   (For a later version, use `v1.0.1`, `v1.1.0`, etc.)
3. On GitHub, open the **Actions** tab to watch it build (about 5–10 minutes),
   or just wait. When it finishes, the installers are on the **Releases** page:
   `https://github.com/nnajioforobinna-cell/homily-manager/releases`

You can also trigger it from the **Actions** tab → *Build desktop installers* →
**Run workflow**.

## Installing (the app is unsigned, so there is a one-time step)

These installers are not code-signed with a paid Apple/Microsoft certificate, so
the system warns the first time. This is normal for a self-built app.

- **Mac:** open the `.dmg`, drag **Homily Manager** to Applications. The first
  time you open it, **right-click the app → Open**, then **Open** again. After
  that it opens normally.
- **Windows:** run the `.exe` setup. If SmartScreen warns, click **More info →
  Run anyway**.

## Changing the web address

If your hosted address ever changes, update it in **two** files, then push a new
tag to rebuild:

- `src-tauri/tauri.conf.json` → `app.windows[0].url`
- `dist/index.html` → the two `pythonanywhere.com` links
