# Proxmox Lab Demo (Django)

A minimal Django site that logs a student in with their **Proxmox account** and shows
their VM's console in an `<iframe>`, next to the lab instructions.

The interesting code is small:

| File | What it does |
|---|---|
| `labs/proxmox.py` | Talks to the Proxmox API: get/renew a login ticket, list VMs, build the console URL, set the `PVEAuthCookie` |
| `labs/backends.py` | Django auth backend: a login succeeds if Proxmox gives us a ticket |
| `labs/views.py` | Login (stores the ticket + sets the cookie), workspace page, ticket refresh, logout |
| `labs/templates/labs/workspace.html` | The Labs / Tasks / VM page, **including the JavaScript that builds it and loads the VM into the iframe** (see *Who does what: Django vs. JavaScript*) |
| `labs/sample_data.py` | Hard-coded labs; each one names the `vmid` it runs on |
| `labs/management/commands/runserver.py` | Replaces `manage.py runserver` with an HTTPS version (see *How the login works* for why) |

No extra Proxmox library is used. It's only two API calls, made with `requests`.

Want the labs and tasks to come from the database, drawn with React? See
[REACT_GUIDE.md](REACT_GUIDE.md).

Building your own project and using this one as a guide? See
[Using this in your own Django project](#using-this-in-your-own-django-project). It lists
every piece you need to copy, including one setting where **order matters**.

### Terms used in this README

| Term | Meaning |
|---|---|
| **Ticket** | What Proxmox gives you when you log in through its API: a long string that proves who you are, valid for 2 hours. Like a session ID. |
| **`PVEAuthCookie`** | The browser cookie Proxmox's own web pages use to hold that ticket. |
| **Realm** | The part of a Proxmox username after the `@`, saying where the account lives. `student1@pve` is in the `pve` realm (Proxmox's own user list). |
| **`<iframe>`** | An HTML element that shows another web page inside your page. Here it shows the Proxmox console. |
| **Self-signed certificate** | An HTTPS certificate you make yourself instead of getting one from a trusted authority. It encrypts traffic fine, but browsers warn about it because nobody vouches for it. |
| **venv (virtual environment)** | A folder (`.venv/`) holding this project's own copy of Python packages, so they don't mix with other projects. |
| **`.env` file** | A text file of `NAME=value` settings that the project reads at startup. It holds secrets and per-computer settings and is never committed to Git. |

> [!IMPORTANT]
> **In this project, `python manage.py runserver` serves HTTPS, not HTTP.** Browse to
> **`https://`**`labs.example.com:8000` (with your own hostname, see step 4), and expect a
> one-time certificate warning. Step 5 explains why.

## How the login works

```
Browser                       Django (labs.example.com)              Proxmox (pve.example.com)
  |  POST /login/ user+pass  ->  |                                         |
  |                              |  POST /api2/json/access/ticket       ->  |
  |                              |  <-  ticket (valid 2h)                   |
  |  <- 302 + Set-Cookie:        |                                         |
  |     PVEAuthCookie=<ticket>;  |                                         |
  |     Domain=.example.com      |                                         |
  |  GET /  (workspace)       -> |  GET /cluster/resources (with ticket) -> |
  |  <- page with <iframe src="https://pve.example.com/?console=kvm...">    |
  |  iframe GET, browser sends PVEAuthCookie  --------------------------->  |
  |  <- logged-in noVNC console  <---------------------------------------   |
```

The key idea: **Proxmox's web UI uses a cookie named `PVEAuthCookie` that contains
the ticket.** If the browser has that cookie when the iframe loads the console page,
the console is already logged in.

A website can only set cookies for its own domain or a parent of it. So **Django and
Proxmox must share a parent domain** (here `example.com`), and Django sets the cookie on
`.example.com`. That's why you must use hostnames, not IP addresses.

**Both sites must also use HTTPS.** Browsers treat `http://labs.example.com` and
`https://pve.example.com` as *different* sites because the scheme differs, and then
they won't send the cookie inside the iframe. The console shows up but isn't logged
in. So in this project, `runserver` is replaced with a version that serves HTTPS
(`labs/management/commands/runserver.py`, step 5).

The ticket expires after 2 hours. The workspace page asks Django for a fresh one every
10 minutes (`/proxmox/refresh/`), and Django renews it by sending the old ticket as the
password.

## Who does what: Django vs. JavaScript

If you read only the Python files, it can look like nothing ever puts the VM on the page.
That's because **a lot of the work happens in JavaScript in the browser**. The script is
at the bottom of `labs/templates/labs/workspace.html`, inline in the template, not in a
separate `.js` file like most projects use.

**Django (Python, on the server)** does everything that needs a secret or talks to Proxmox:

1. Checks the student's username and password with Proxmox and gets the ticket
   (`backends.py`, `proxmox.py`).
2. Gives the browser the `PVEAuthCookie` (`views.py`, `proxmox.set_auth_cookie`).
3. When the workspace page is requested (`WorkspaceView`), asks Proxmox which VMs the
   student can use and builds each VM's console URL.
4. Sends the page with that data embedded as JSON, using Django's `json_script` filter:

   ```html
   {{ labs|json_script:"labs-data" }}   →  <script id="labs-data" type="application/json">[...]</script>
   {{ vms|json_script:"vms-data" }}     →  <script id="vms-data" type="application/json">{...}</script>
   ```

   These tags just hold data. The page doesn't show them.

**JavaScript (in the browser)** then takes that data and makes the page work:

| Function in `workspace.html` | What it does |
|---|---|
| (top of the script) | Reads the two JSON blocks into the `labs` and `vms` variables |
| `renderLabList()` | Builds the Labs sidebar |
| `renderTasks()` | Builds the task list with instructions and question forms for the selected lab |
| `loadVm()` | Finds the lab's VM in `vms` and **sets the iframe's `src` to its console URL. This is the line that shows the VM.** If the student can't use that VM, it shows the "not available" message instead. |
| `selectLab()` | Runs the three functions above when a lab is clicked |
| `setInterval(...)` (bottom) | Every 10 minutes, sends a `POST` to `/proxmox/refresh/` (`RefreshTicketView`) so Django renews the ticket and re-sends the cookie. Without this, the console stops working after 2 hours. |

Two things to know:

- **Task answers are not saved anywhere yet.** Clicking *Submit* marks the task done in
  the browser and prints the answers to the browser console (F12 → *Console*). The
  progress resets on reload. Saving them would need a Django model and a view for the
  JavaScript to `POST` to; the `TODO` in the submit handler marks the spot.
- **Why inline?** It keeps the sample in one file, and the script can use Django's `url`
  template tag to get the refresh and login URLs. In your own project you can move it to
  a static file (e.g. `labs/static/labs/workspace.js`, loaded with `{% static %}`). If you
  do, pass those two URLs in some other way, for example as `data-` attributes on an
  element, because template tags don't work inside static files.

## Getting started

### Prerequisites

- **Python 3.10 or newer** (Django 5.2 requires it). Check with `python --version`.
- **Git**
- A **Proxmox VE** server, and a Proxmox account that can open the console of at least
  one VM (see step 1).

### Which terminal?

The commands below are written for **Git Bash on Windows**. They also work in the macOS
and Linux terminal, except where a step says otherwise. The few commands that differ:

| Step | Git Bash (Windows) | macOS / Linux | PowerShell (Windows) |
|---|---|---|---|
| Create the venv | `python -m venv .venv` | `python3 -m venv .venv` | `python -m venv .venv` |
| Activate the venv | `source .venv/Scripts/activate` | `source .venv/bin/activate` | `.venv\Scripts\activate` |
| Copy a file | `cp` | `cp` | `copy` |
| Commands that ask for input (e.g. `createsuperuser`) | prefix with `winpty` if it hangs or says "not running in a TTY" | as-is | as-is |

**Opening Git Bash in the project folder:**

- **In VS Code:** *Terminal → New Terminal*, then click the **⌄** next to the **+** in the
  terminal panel and choose **Git Bash**. It opens in the folder VS Code has open.
- **From File Explorer:** right-click inside the project folder → **Open Git Bash here**
  (on Windows 11, you may need *Show more options* first).

Git Bash tips:

- Use **`python`**, not `python3`. On Windows, `python3` often opens the Microsoft Store
  instead of running Python.
- Windows puts the venv's scripts in **`.venv/Scripts/`**, not `.venv/bin/` like on
  macOS/Linux, even inside Git Bash.
- Use forward slashes in paths (`.venv/Scripts/activate`). Backslashes don't work in bash.

### 1. Set up Proxmox accounts (instructor, once)

> **Students: skip this step.** Your instructor has done it and will give you a Proxmox
> username and password.

On the Proxmox host shell, create a user for each student in the `pve` realm and give
them access to *only* their VM:

```bash
pveum user add student1@pve --password 'ChangeMe123!'
pveum acl modify /vms/100 --users student1@pve --roles PVEVMUser
```

`PVEVMUser` includes `VM.Console` (open the console) and `VM.Audit` (see the VM in
the list). Without them the VM won't show up for that student.

The VM ids used by the sample labs are set in `labs/sample_data.py` (`vmid: 100` and
`101`). Change them to match your VMs.

### 2. Get the code and install dependencies

```bash
git clone https://github.com/dbarneskvcc/proxmox_lab_demo.git
cd proxmox_lab_demo
python -m venv .venv
source .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

When the virtual environment is active, your prompt shows `(.venv)`. In Git Bash it
appears on the line above the `$`. Run every `python` command below with it active.

PowerShell users: activate with `.venv\Scripts\activate`. If PowerShell says *running
scripts is disabled on this system*, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
once, then activate again.

### 3. Create your `.env` file

All machine-specific and secret settings live in a `.env` file next to `manage.py`,
read with [environs](https://pypi.org/project/environs/). It is ignored by Git, so it
is never committed.

```bash
cp .env.example .env
```

Open `.env` in your editor (e.g. `code .env` for VS Code) and fill it in. Every setting
is explained in `.env.example`.

`.env` format rules: one setting per line as `NAME=value`, **no spaces around `=`** and
**no quotes** around the value. Lines starting with `#` are comments.

```
SECRET_KEY=abc123...        # right
SECRET_KEY = "abc123..."    # wrong: spaces and quotes
```

- **`SECRET_KEY`:** generate your own and paste it in:
  ```bash
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```
- **`PROXMOX_*` and `ALLOWED_HOSTS`:** your instructor will give you these lines. Step 4
  explains what they mean and how to check them.

(Advanced: if a variable with the same name is set in your terminal's environment, it
takes priority over the line in `.env`. You can ignore this unless a setting seems to be
"stuck".)

### 4. Give the site a hostname

This step trips up most people, so take it slowly.

**Why it's needed:** your browser will only send the Proxmox login cookie to sites
that share Proxmox's domain name (see *How the login works*). So you can't browse to
this site as `localhost`. You need to reach it by a name that *looks like* it belongs
to the same domain as Proxmox.

**What a hosts file is:** a small text file on your computer that acts as a private
phone book for domain names. Your computer checks it *before* asking the internet's DNS.
If you add the line `127.0.0.1 labs.example.com`, then on your computer only,
`labs.example.com` means "this computer" (`127.0.0.1` always means "this computer").
That's where your Django site is running.

#### Work out the names: answer three questions

**Question 1: What is the Proxmox server's hostname?**
Open Proxmox in your browser the way you normally do and look at the address bar.
The hostname is the part between `https://` and the next `:` or `/`. Ignore `https://`,
any port like `:8006`, and anything after that (such as `/#v1:0:18...`).

> Example: `https://pve.example.com:8006/#v1:0:18` → hostname **`pve.example.com`**

**Question 2: What is its parent domain?**
Remove the first part of the hostname, up to and including the first dot.

> Example: `pve.example.com` → parent domain **`example.com`**

**Question 3: What name will this site use?**
Put a new first part in front of the parent domain. Use **`labs`** unless your
instructor says otherwise.

> Example: `labs` + `.` + `example.com` → **`labs.example.com`**

More examples:

| Q1: Proxmox address you open | Proxmox hostname | Q2: Parent domain | Q3: Name for this site |
|---|---|---|---|
| `https://pve.example.com` | `pve.example.com` | `example.com` | `labs.example.com` |
| `https://proxmox.lab.example.org:8006` | `proxmox.lab.example.org` | `lab.example.org` | `labs.lab.example.org` |
| `https://192.168.1.50:8006` | *none, it's an IP address* | see *Proxmox only has an IP address* below | |

#### Add the hosts entry

Write down your answer to Question 3, then add **one line** to your hosts file:

```
127.0.0.1     <your answer to Question 3>
```

For the example above, that line is `127.0.0.1     labs.example.com`. Don't include
`https://`, a port, or a trailing `/`. It's just the IP address, some spaces, and the name.

How to open the hosts file:

- **Windows (Git Bash or PowerShell):** Git Bash can't edit this file, because it needs
  Administrator rights. Open **Notepad as Administrator** (Start menu → type Notepad →
  right-click → *Run as administrator*), then File → Open
  `C:\Windows\System32\drivers\etc\hosts`. Change the file type from *Text Documents* to
  *All Files*, or the file won't show up. Add your line at the bottom and save. If saving
  says *access denied*, Notepad wasn't run as Administrator.
- **macOS/Linux:** `sudo nano /etc/hosts`, add the line at the bottom, then save with
  Ctrl+O, Enter, and exit with Ctrl+X.

Lines starting with `#` are comments and are ignored. Don't put `#` in front of your line.

#### Check it worked

```bash
ping -n 1 labs.example.com     # use your name; macOS/Linux: ping -c 1 labs.example.com
```

The output should mention **`127.0.0.1`**, e.g. `Pinging labs.example.com [127.0.0.1]`.
If it shows a different address or *could not find host*, re-check the hosts file for
typos, and make sure it actually saved.

#### Make sure `.env` agrees

The same three answers appear in your `.env`. If your instructor gave you the lines,
check that they match. If you're filling them in yourself, use these values:

| `.env` setting | Value | Example |
|---|---|---|
| `PROXMOX_URL` | `https://` + Proxmox hostname (Q1) + port, if you use one | `https://pve.example.com:8006` |
| `PROXMOX_COOKIE_DOMAIN` | a dot + parent domain (Q2) | `.example.com` |
| `ALLOWED_HOSTS` | your site's name (Q3), plus `localhost,127.0.0.1` | `labs.example.com,localhost,127.0.0.1` |

#### Proxmox only has an IP address

If you open Proxmox with something like `https://192.168.1.50:8006`, there's no domain to
share yet, so make one up. Use names ending in `.test`, a suffix reserved for exactly
this. Add **two** lines to the hosts file: one for Proxmox's real IP and one for your site.

```
192.168.1.50  pve.proxmox.test      # Proxmox's real IP address
127.0.0.1     labs.proxmox.test     # this computer (the Django site)
```

Then in `.env`: `PROXMOX_URL=https://pve.proxmox.test:8006`,
`PROXMOX_COOKIE_DOMAIN=.proxmox.test`, `ALLOWED_HOSTS=labs.proxmox.test,localhost,127.0.0.1`,
and `PROXMOX_VERIFY_SSL=false` (Proxmox's certificate won't match the made-up name).
From now on, open Proxmox as `https://pve.proxmox.test:8006`, not by its IP.

#### Accept the certificate (only if you get a warning)

Open your `PROXMOX_URL` in the browser once. If you get a certificate warning
(Proxmox's default self-signed certificate), accept it. An iframe can't show that
warning, so the console would just stay blank.

### 5. Set up the database and run the site (over HTTPS)

```bash
python manage.py migrate
python manage.py runserver labs.example.com:8000
```

Replace `labs.example.com` with your answer to Question 3 from step 4, both in the
command above and in the browser.

`migrate` creates the local database file `db.sqlite3` with the tables Django needs for
logins and sessions. You only need to run it the first time, and again after pulling
code that changes the database. The site doesn't define any database tables of its own.

> [!IMPORTANT]
> **This `runserver` is not the usual one: it serves HTTPS.** The project replaces
> Django's `runserver` with its own version (`labs/management/commands/runserver.py`),
> because over plain HTTP the browser won't send the Proxmox login cookie into the iframe
> (see *How the login works*). You run it the same way as always, but:
>
> - the terminal says `Starting development server at https://...` (with an **`s`**)
> - you must browse to **`https://`**. Typing `http://` gives an error page (see
>   Troubleshooting).
> - the first time, it creates a self-signed certificate in the `certs/` folder (ignored
>   by Git), valid for the names in `ALLOWED_HOSTS`.

Then browse to **https://labs.example.com:8000**, with your name.

- Your browser will warn that the connection isn't private. That's expected, because the
  certificate was made on your own computer rather than issued by a real authority. Click
  **Advanced** → **Continue to labs.example.com (unsafe)**. You only need to do this once.
- Don't use `localhost` or `127.0.0.1`, or the cookie domain won't match.

Log in with your Proxmox username (e.g. `student1`) and password. The VM's console
should appear on the right.

Optional: create a local account for the Django admin at `/admin/` (not needed to use
the labs). In Git Bash, prefix it with `winpty` so the password prompt works:

```bash
winpty python manage.py createsuperuser   # macOS/Linux/PowerShell: drop "winpty"
```

### Running it again later

Open Git Bash in the project folder and run:

```bash
source .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
python manage.py runserver labs.example.com:8000
```

Then browse to **https://labs.example.com:8000** (your name; remember the `s`).

Stop the server with **Ctrl+C**, and leave the venv with `deactivate`. After pulling new
code, run `pip install -r requirements.txt` and `python manage.py migrate` again in case
anything changed.

## Using this in your own Django project

If you're adding Proxmox login to your own project instead of building on this one, these
are the pieces to copy. The app here is called `labs`. If yours has a different name,
replace `labs` everywhere below (including in dotted paths like `labs.backends.ProxmoxBackend`).

1. **Packages:** install `requests`, `environs` and `cryptography`
   (`pip install requests environs cryptography`) and add them to your `requirements.txt`.

2. **The Proxmox code:** copy `labs/proxmox.py` (API calls and the cookie) and
   `labs/backends.py` (the login check) into your app.

3. **The HTTPS `runserver`:** copy `labs/management/commands/runserver.py`. The folder
   structure must be exactly this, **including the two empty `__init__.py` files**.
   Without them Django won't find the command.

   ```
   your_app/
       management/
           __init__.py          <- empty file
           commands/
               __init__.py      <- empty file
               runserver.py
   ```

4. **`INSTALLED_APPS`: order matters.** Your app must be listed **before**
   `"django.contrib.staticfiles"`:

   ```python
   INSTALLED_APPS = [
       "django.contrib.admin",
       "django.contrib.auth",
       "django.contrib.contenttypes",
       "django.contrib.sessions",
       "django.contrib.messages",
       "labs",  # <- your app, BEFORE staticfiles
       "django.contrib.staticfiles",
   ]
   ```

   **Why:** `django.contrib.staticfiles` also has its own `runserver` command (it adds
   static file serving to Django's normal one). When two apps provide a command with the
   same name, Django uses the one from the app listed **first**. If staticfiles comes
   first, you get the normal plain-HTTP `runserver`. There's no error, but the console
   won't be logged in. You can check which one you're getting: the terminal should say
   `Starting development server at https://...`. Our `runserver` is built on top of the
   staticfiles one, so static files still work.

5. **Settings:** copy the end of `django_project/settings.py`, from `# Authentication`
   down. That's `AUTHENTICATION_BACKENDS`, `LOGIN_URL`/`LOGIN_REDIRECT_URL`/`LOGOUT_REDIRECT_URL`,
   and all the `PROXMOX_*` settings. Also copy the `env = Env()` / `env.read_env(...)` lines
   from the top so `.env` is read, plus `.env.example` and the `.env` / `certs/` lines from
   `.gitignore`.

6. **Views and URLs:** use `labs/views.py` and `labs/urls.py` as a model. The important parts:
   - after login, save the ticket in the session **and** call `proxmox.set_auth_cookie(...)`
     on the response (`ProxmoxLoginView.form_valid`)
   - set the cookie again on the page that shows the iframe (`WorkspaceView.get`)
   - a view the page can call to renew the ticket (`RefreshTicketView`), plus the JavaScript
     at the bottom of `workspace.html` that calls it every 10 minutes
   - clear the cookie on logout (`ProxmoxLogoutView`)

7. **The page's JavaScript:** the iframe only shows the VM because JavaScript sets its
   `src` to the URL from `proxmox.console_url(vm)`, and the ticket only stays fresh because
   JavaScript calls the refresh view. Copy or adapt the script at the bottom of
   `workspace.html` (see *Who does what: Django vs. JavaScript*). If you show a single VM,
   you can skip most of it and render the iframe directly in the template:
   `<iframe src="{{ vm.console_url }}"></iframe>`. But you still need the refresh
   `setInterval` code.

Then follow steps 3–5 of *Getting started* (`.env`, hosts file, `runserver`). They're the
same for any project.

## Troubleshooting

**Where to look when something goes wrong:**

- **The terminal running the server.** Every request is printed there, plus errors. For
  example, a failed Proxmox login prints `Proxmox login failed for student1: ...` with
  the reason.
- **The browser's developer tools** (press **F12**). The *Console* tab shows JavaScript
  errors; the *Network* tab shows each request and its status code (e.g. 401, 404);
  *Application → Cookies* shows the cookies the browser has.
- **The message on the page itself.** The login page and the workspace both show
  Proxmox errors in a red box.

| Symptom | Likely cause |
|---|---|
| Login page: "Could not reach Proxmox…" | Django's machine can't resolve or reach the Proxmox server. Check `PROXMOX_URL` in `.env`, the hosts file and the firewall. |
| Login page: "Proxmox rejected the username or password" | Wrong password, or the user is in a different realm. Try `student1@pve` explicitly. |
| "VM 100 isn't available to your Proxmox account" | Missing ACL. Run the `pveum acl modify` command from step 1 for that VM. |
| Error: `Environment variable "SECRET_KEY" not set` (or another variable) | There is no `.env` file next to `manage.py`, or that line is missing. See step 3. |
| `ping` doesn't show `127.0.0.1` for your site's name | The hosts file didn't save (Notepad not run as Administrator), the name has a typo, or the line starts with `#`. |
| `Invalid HTTP_HOST header` | Add the hostname you browse with to `ALLOWED_HOSTS` in `.env`. |
| `bash: .venv/bin/activate: No such file or directory` | You're on Windows. In Git Bash use `source .venv/Scripts/activate`. |
| `python3` opens the Microsoft Store, or `Python was not found` | Use `python` instead of `python3`. If `python` fails too, reinstall Python with *Add python.exe to PATH* ticked, then reopen Git Bash. |
| `ModuleNotFoundError: No module named 'django'` (or `environs`) | The venv isn't active in this terminal. Activate it (step 2) and try again. |
| `createsuperuser` hangs or says "not running in a TTY" | Git Bash needs `winpty python manage.py createsuperuser`. |
| iframe is blank | Certificate not accepted yet. Click the ↗ button to open the console in a tab and accept it. |
| iframe shows the console but it says "401", "No ticket", or fails to connect | The browser isn't sending the cookie to Proxmox. Check, in order: (1) the address bar starts with **`https://`** and the terminal said `Starting development server at https://...` (step 5); (2) you browsed to your `labs.…` name, not `localhost` or an IP; (3) in DevTools (F12) → Application → Cookies, `PVEAuthCookie` exists for your `PROXMOX_COOKIE_DOMAIN`. |
| Browser: "This page isn't working" / `ERR_EMPTY_RESPONSE` | You typed `http://`. This project's server only speaks HTTPS, so use `https://labs.example.com:8000`. |
| Browser: "Your connection isn't private" / `NET::ERR_CERT_AUTHORITY_INVALID` | Expected with the self-signed dev certificate. Click **Advanced** → **Continue**. |
| Browser: `NET::ERR_CERT_COMMON_NAME_INVALID` | The certificate was made before you set `ALLOWED_HOSTS`. Stop the server, delete the files in `certs/` (`rm certs/dev.*`), and start it again to make a new one. |
| Terminal says `Starting development server at http://...` (no `s`) | Django's own `runserver` ran instead of the project's. Make sure `"labs"` is listed **before** `"django.contrib.staticfiles"` in `INSTALLED_APPS` (see *Using this in your own Django project*, item 4), and that `management/__init__.py` and `management/commands/__init__.py` exist. |
| The site behaves strangely, or changes don't show up, after restarting the server | An old server may still be running on port 8000 (on Windows a second server can start on the same port without an error). Close any other terminals running the site, or find and stop it: `netstat -ano \| grep :8000` shows the process id, then `taskkill //PID <id> //F` in Git Bash. |

## Going further

- **Production:** serve Django behind a real web server (e.g. nginx with a real
  certificate) instead of `runserver`, use real DNS names under one domain, and
  verify the Proxmox certificate (`PROXMOX_VERIFY_SSL` set to a copy of
  `/etc/pve/pve-root-ca.pem`).
- **Calling write APIs (start/reset a VM):** use the stored ticket as the cookie *and*
  send the `csrf_token` saved in the session as a `CSRFPreventionToken` header.
- **Two-factor accounts** aren't handled. Proxmox returns `NeedTFA` and the login is refused.
