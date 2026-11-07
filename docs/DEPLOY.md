# Putting Homily Manager online (iPad and phone)

This guide puts the app on the internet so you can open it from your iPad, your
phone, or any computer — even when your mac is off. It keeps your one SQLite
database (all your homilies), and it adds a password, because the funeral records
hold personal details and must not be open to the public.

You only do this setup once. After that you just open a web address and sign in.

The host recommended here is **PythonAnywhere**, because it runs Flask apps
directly, keeps your database file safe between restarts, includes HTTPS, and has
a free plan. (An alternative, Render, is noted at the end.)

---

## What you need first

1. **The app is on GitHub already:** `https://github.com/nnajioforobinna-cell/homily-manager`
2. **A copy of your database.** In the app on your mac, open **Backup → Download a
   backup**. That file (`homilies-YYYYMMDD-HHMMSS.db`) is your whole library; you
   will upload it to the host. Keep it handy.
3. **A password** you will use to sign in, and a **secret key** (a long random
   string). To make a secret key, run this on your mac and copy the output:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

---

## Step by step (PythonAnywhere)

### 1. Make an account
Go to **https://www.pythonanywhere.com** and create an account. The free
("Beginner") plan works. The **$5/month "Hacker"** plan is worth it later: it
removes the free plan's monthly "keep alive" click and lets you use your own web
address, but start free if you like.

### 2. Get the code onto the host
On PythonAnywhere, open **Consoles → Bash** and run:
```bash
git clone https://github.com/nnajioforobinna-cell/homily-manager.git
```

### 3. Install what the app needs
Still in the Bash console:
```bash
mkvirtualenv --python=python3.11 homily
pip install -r homily-manager/app/requirements.txt
```
(The prompt will show `(homily)` once the environment is active.)

### 4. Put your database in place
Open the **Files** tab, go to
`homily-manager/app/database/`, and **Upload** the backup file you downloaded in
step 0. Then rename it to exactly **`homilies.db`** (use the pencil/rename icon).
If you skip this, the app simply starts with an empty library.

### 5. Create the web app
Open the **Web** tab → **Add a new web app** → **Manual configuration** →
**Python 3.11**.

### 6. Point it at the app and set your password
On the Web tab:

- **Virtualenv:** enter `/home/USERNAME/.virtualenvs/homily`
  (replace `USERNAME` with your PythonAnywhere username).
- **WSGI configuration file:** click the link to edit it, delete everything in it,
  and paste this (replacing `USERNAME`, the password, and the secret key):
  ```python
  import os, sys

  os.environ["HOMILY_PASSWORD"]   = "choose-a-strong-password"
  os.environ["HOMILY_SECRET_KEY"] = "paste-the-long-random-string-here"
  os.environ["HOMILY_DB"] = "/home/USERNAME/homily-manager/app/database/homilies.db"

  path = "/home/USERNAME/homily-manager/app"
  if path not in sys.path:
      sys.path.insert(0, path)

  from server import app as application
  ```
  Save it.

### 7. Start it
Back on the **Web** tab, click the big green **Reload** button. Then open
**`https://USERNAME.pythonanywhere.com`** on your iPad or phone, and sign in with
the password you set.

Tip: on the iPad/phone, use the browser's **"Add to Home Screen"** so it opens
like an app.

---

## Keeping it up to date

- **New homily files to import:** upload them, or import on your mac and upload a
  fresh database backup (step 0 → step 4), then **Reload** on the Web tab.
- **App improvements (from here):** in the Bash console,
  `cd homily-manager && git pull`, then **Reload**.
- **Back up the online database** now and then from the app's **Backup** page, the
  same as on your mac.

---

## Important notes on safety

- **Always set `HOMILY_PASSWORD`** online. Without it the app has no login — fine
  on your own mac, not fine on the public internet. Use a strong password.
- PythonAnywhere serves the site over **HTTPS** automatically, so your sign-in and
  your homilies travel encrypted.
- Your database lives only on the host and on your mac backups — it is never put
  in GitHub (the repository holds the code only).

---

## Alternative host: Render

Render deploys straight from GitHub and is a little more automatic, but its free
plan erases the database on every restart. To keep your library you must either
add a **paid persistent disk** (about $1/month on a paid instance) or move to a
hosted PostgreSQL database (a larger change). The app is ready for Render too: it
includes a `Procfile` and uses `gunicorn`. If you prefer Render, say so and it can
be set up, but PythonAnywhere is the simpler home for this SQLite-based app.
