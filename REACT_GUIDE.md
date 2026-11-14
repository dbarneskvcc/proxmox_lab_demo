# Guide: Load the Labs and Tasks with React and Django REST Framework

Right now the labs and tasks come from a hard-coded Python list (`labs/sample_data.py`), and
plain JavaScript in `workspace.html` draws them. This guide changes that so:

- **Django** still makes the page: the navbar, the login, the Proxmox cookie, and the list of
  VMs the student can use.
- **The labs and tasks are stored in the database**, so you can edit them in the Django admin.
- **Django REST Framework (DRF)** sends them to the browser as JSON.
- **React** draws the Labs, Tasks and VM columns, and asks the API for a lab's tasks when the
  student clicks it.

The page will look and work exactly as it does now. Only *how* it's built changes.

This guide assumes you've finished the main [README](README.md) and the site already works:
you can log in and see the VM console. It also assumes you know React basics (components,
props, `useState`, `useEffect`). Everything else is explained as it comes up.

> [!IMPORTANT]
> **This is not built the way most React tutorials build things.** In most tutorials React
> runs the whole website. Here, Django runs the website and React draws *one part* of *one
> page*. Read [How this differs from a React tutorial](#how-this-differs-from-a-react-tutorial)
> before you start. It will save you a lot of confusion when something here doesn't match what
> you've seen before.

## Contents

- [The big picture](#the-big-picture)
- [How this differs from a React tutorial](#how-this-differs-from-a-react-tutorial)
- [Words you'll see](#words-youll-see)
- [Part 1: The API (Django REST Framework)](#part-1-the-api-django-rest-framework)
- [Part 2: The React app (Vite)](#part-2-the-react-app-vite)
- [Part 3: Connect React to the Django page](#part-3-connect-react-to-the-django-page)
- [Part 4: Working on it day to day](#part-4-working-on-it-day-to-day)
- [Troubleshooting](#troubleshooting)
- [Where to go next](#where-to-go-next)
- [Further reading](#further-reading)

## The big picture

### Who draws which part of the page

```
+---------------------------------------------------------------------------+
|  Navbar: user name, Log out, hide-panels button       <- Django template  |
+---------------------------------------------------------------------------+
|  <div id="react-root">                                <- React, from here |
|  +--------------+---------------------+----------------------------------+ |
|  | LabList      | TaskList            | VmPane                           | |
|  | (column 1)   | (column 2)          | (column 3)                       | |
|  |              |   Question          |   <iframe> -> Proxmox console    | |
|  |              |   Question ...      |                                  | |
|  +--------------+---------------------+----------------------------------+ |
+---------------------------------------------------------------------------+
   Also in the template, not drawn: the VM list as JSON, and a small plain
   script that renews the Proxmox ticket every 10 minutes.
```

Django sends the whole page as HTML, but the big `<div id="react-root">` arrives **empty**.
React fills it in once the page has loaded in the browser.

### What happens when a student opens the page

```
Browser                                   Django (labs.example.com)
  |  GET /  ---------------------------->  WorkspaceView: logs in to Proxmox, gets the
  |                                        student's VMs, renders workspace.html
  |  <- HTML page: navbar, an empty <div id="react-root">, the VM list as JSON,
  |     and <script src="/static/labs/react/workspace.js">  (the React app)
  |
  |  GET /static/labs/react/workspace.js -> (a plain file; Django just sends it)
  |
  |  React starts, then:
  |  GET /api/labs/  --------------------> LabListAPIView  (just names for the sidebar)
  |  <- [{"id": 1, "title": "Linux Basics", "icon": "bi-terminal", "task_count": 3}, ...]
  |
  |  GET /api/labs/1/  ------------------> LabDetailAPIView (one lab, all its tasks)
  |  <- {"id": 1, "title": ..., "vmid": 100, "tasks": [{..., "questions": [...]}]}
  |
  |  (student clicks another lab)
  |  GET /api/labs/2/  ------------------> LabDetailAPIView
  |
  |  The iframe loads the console straight from Proxmox, with the PVEAuthCookie
  |  Django set earlier (the README explains this part; React doesn't change it).
```

**Why two API endpoints instead of one?** To send as little data as possible. The sidebar
only needs each lab's name, icon and number of tasks. The full instructions and questions
for a lab are only sent when the student opens that lab. With many labs, the first request
stays small and the page appears quickly.

**Why doesn't the VM list come from the API too?** Getting it means calling Proxmox with the
student's ticket. Django already does that when it makes the page (see the README), so it
puts the VM list straight into the page and React just reads it. That's one less API call,
and the Proxmox code doesn't change at all.

### Two different times: building and running

There's one more idea that tutorials usually hide from you:

```
WHILE YOU DEVELOP, on your computer:
  frontend/src/*.jsx  --[ Vite, which runs on Node.js ]-->  labs/static/labs/react/workspace.js

WHILE THE SITE RUNS:
  Browser  <-->  Django   (Django sends workspace.js like any other static file)
```

**Node.js and Vite are only build tools here.** They turn your `.jsx` files into one
`workspace.js` file, and then their job is done. The running website is still just Django;
Node.js isn't involved at all. A server running this site wouldn't even need Node.js
installed, as long as someone ran the build first.

### What you'll add or change

| File | New or changed | What it's for |
|---|---|---|
| `labs/models.py` | changed | `Lab`, `Task` and `Question` database tables |
| `labs/admin.py` | changed | Edit labs, tasks and questions in the Django admin |
| `labs/management/commands/load_sample_labs.py` | new | Copies `sample_data.py` into the database once |
| `labs/serializers.py` | new | DRF: turns the models into JSON |
| `labs/api_views.py` | new | DRF: the two API endpoints |
| `labs/urls.py` | changed | URLs for the API |
| `django_project/settings.py` | changed | Add DRF and its settings |
| `frontend/` | new folder | The React app's source code. The browser never sees these files directly. |
| `labs/static/labs/react/workspace.js` | new, **generated** | The built React app that the browser loads. Made by Vite; never edit it by hand. |
| `labs/templates/labs/workspace.html` | changed | Swaps the plain JavaScript for the React app |
| `labs/views.py` | changed | Stops sending the hard-coded labs |

## How this differs from a React tutorial

Most React tutorials (and the official ["Creating a React App"](https://react.dev/learn/creating-a-react-app)
page) build a **single-page application** ([SPA](https://developer.mozilla.org/en-US/docs/Glossary/SPA)):
React runs the *entire* website, and the backend is a separate program that only answers API
requests. This project uses React the other way the React docs describe:
[adding React to part of an existing page](https://react.dev/learn/add-react-to-an-existing-project).
Some people call this pattern a [React "island"](https://www.patterns.dev/vanilla/islands-architecture/):
an interactive area inside a page the server made.

### Side by side

| | Typical React tutorial (React runs everything) | This project (React draws one part of a Django page) |
|---|---|---|
| **Who makes the HTML page** | Vite, from an `index.html` file. React draws everything in it. | A Django template. React draws only what's inside `<div id="react-root">`. |
| **Servers while developing** | Two: Vite's dev server (e.g. `localhost:5173`) for React, plus the backend API on another port. | One: Django. Vite only builds a file. |
| **Commands you run** | `npm run dev` | `python manage.py runserver` plus `npm run watch` (Part 4) |
| **Starting the project** | `npm create vite@latest` | `package.json` and `vite.config.js` written by hand (step 9) |
| **Moving between pages** | React Router, in the browser | Django URLs. Only the workspace page uses React. |
| **Logging in** | A login form in React, which stores a token (often a JWT) and sends it with each request | Django's normal login page and session cookie. The browser sends the cookie automatically. |
| **CORS settings** | Needed, because React and the API are on different ports | Not needed: everything is on one site |
| **Where the data comes from** | All from the API | Labs and tasks from the API. The VM list is put in the page by Django. |
| **CSS** | `import './App.css'` inside components | One `<style>` block in the Django template. Components use the same Bootstrap class names. |
| **Forms** | "Controlled" inputs, with a `useState` for each field | "Uncontrolled" inputs, read with `FormData` on submit (step 11) |

### Why it's built this way

**1. The Proxmox console depends on Django making the page.** The README explains that the
console in the iframe only logs in if the browser has the `PVEAuthCookie`. Django sets that
cookie when it logs the student in and when it sends the workspace page, from
`https://labs.example.com`, which shares a parent domain with Proxmox. A separate React dev
server on `localhost:5173` would be a different site. Getting the cookie right from there is
much harder, and it's the exact problem the README's hostname and HTTPS steps solved. Keeping
Django in charge of the page means none of that changes.

**2. Django already does the hard parts well.** Login, sessions, the admin, the Proxmox calls,
and CSRF protection already work. Rewriting them in React would be a lot of work for no gain.
React is used only where it helps: the part of the page that changes a lot while the student
uses it.

**3. One site means no CORS and no tokens.** When React and the API come from the same site,
the browser treats API requests like any other request to that site: it sends the Django
session cookie, and no [CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)
setup is needed. Tutorials need tokens and CORS *because* their React app and API are on
different ports, which browsers count as different sites.

**4. This is common in real projects.** Many sites that started with server-made pages
(Django, Rails, PHP) add React to the parts that need it, rather than rewriting everything.
Knowing how to do both is useful.

**What this means for you:** tutorial code is still useful for the *inside* of components
(state, effects, props, lists). Be careful copying the *setup* (project creation, routing,
login, fetching from `localhost:8000`, CORS), because it assumes the other architecture.

## Words you'll see

| Term | Meaning |
|---|---|
| **API** | URLs that return data (here JSON) instead of web pages, for code to use. |
| **Endpoint** | One API URL, such as `/api/labs/`. |
| **[JSON](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Scripting/JSON)** | A text format for data that looks like JavaScript objects and lists. |
| **[Django REST Framework (DRF)](https://www.django-rest-framework.org/tutorial/quickstart/)** | A Django package that makes building APIs easier. |
| **Serializer** | A DRF class that turns a model (a database row) into JSON. Similar to a Django form, but for data going out. |
| **[Node.js](https://nodejs.org/en/learn/getting-started/introduction-to-nodejs)** | A program that runs JavaScript outside the browser. Vite needs it. Here it's only used on your computer while you build; the website itself runs on Django. |
| **[npm](https://docs.npmjs.com/about-npm)** | Node's package installer, like `pip` for Python. It comes with Node.js. |
| **[`package.json`](https://docs.npmjs.com/cli/configuring-npm/package-json)** | npm's list of the packages a project needs, like `requirements.txt`. |
| **`node_modules/`** | The folder where npm installs packages, like `.venv/`. Never commit it. |
| **[Vite](https://vite.dev/guide/)** | A build tool. It turns your React code (JSX, many files, imports from npm) into one plain `.js` file a browser can run. |
| **[JSX](https://react.dev/learn/writing-markup-with-jsx)** | The HTML-like syntax inside React components (`<div className="...">`). Browsers can't run it directly, which is why Vite is needed. |
| **Build** | Running Vite to produce that `.js` file. |
| **Bundle** | The single file a build produces, with your code and every package it imports (React too) joined together. |
| **[Static files](https://docs.djangoproject.com/en/5.2/howto/static-files/)** | Files Django sends to the browser unchanged: `.js`, `.css`, images. Django finds them in each app's `static/` folder. |
| **SPA (single-page application)** | A site where React runs everything in the browser. What most tutorials build, and *not* what this project is. |

## Part 1: The API (Django REST Framework)

Do Part 1 first and check it works before touching any JavaScript. It's much easier to fix
problems one half at a time: if the API works in the browser (step 7), any later problem
must be on the React side.

Activate your venv first, as always (`source .venv/Scripts/activate` in Git Bash).

### 1. Install Django REST Framework

```bash
pip install djangorestframework
```

Add it to `requirements.txt` so others get it too:

```
djangorestframework>=3.15
```

**Why DRF instead of plain Django views?** You *could* write a normal view that returns
`JsonResponse(...)`. DRF does the repetitive parts for you: turning models into JSON
(serializers), checking who's allowed (permissions), and a web page for trying the API in
your browser (step 7). It's also what most Django + React projects use, so it's worth
knowing.

In `django_project/settings.py`, add `"rest_framework"` to `INSTALLED_APPS`. Put it **after**
`"django.contrib.staticfiles"`. Remember that `"labs"` must stay **before** staticfiles (the
README's *Using this in your own Django project* explains why).

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "labs",
    "django.contrib.staticfiles",
    "rest_framework",
]
```

Then add this below `LOGOUT_REDIRECT_URL = "login"`:

```python
# Django REST Framework
# Only logged-in students can read the API. The React code runs on the same site,
# so the browser's normal Django login (session cookie) is what authenticates it.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
```

**Why session login and not tokens?** DRF supports several ways for an API to know who's
asking ([authentication](https://www.django-rest-framework.org/api-guide/authentication/)).
Tutorials usually use tokens or JWTs, because their React app is on a different site from
the API and can't use Django's login cookie. Here the student is already logged in to
Django, the React code runs on a page from the same site, and the browser sends the login
cookie with every request React makes, just as it does for normal pages.
`SessionAuthentication` simply uses that.
[`IsAuthenticated`](https://www.django-rest-framework.org/api-guide/permissions/) then refuses
anyone who isn't logged in, so the lab content isn't public.

### 2. Create the models

**Why move the labs into the database at all?** While they're in a Python file, only someone
editing code can change them. As database rows, an instructor can add and edit labs in the
admin, and DRF can work with them directly.

These three models hold the same data as `sample_data.py`: a **Lab** has many **Tasks**, and a
**Task** has many **Questions**. Replace the contents of `labs/models.py`:

```python
from django.db import models


class Lab(models.Model):
    title = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default="bi-terminal")  # a Bootstrap Icons class
    description = models.TextField(blank=True)
    vmid = models.PositiveIntegerField(help_text="Proxmox VM id this lab runs on")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class Task(models.Model):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    instructions = models.TextField(help_text="HTML is allowed")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class Question(models.Model):
    KIND_CHOICES = [("text", "Short answer"), ("textarea", "Long answer"), ("radio", "Multiple choice")]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="questions")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="text")
    label = models.CharField(max_length=300, help_text="HTML is allowed")
    options = models.JSONField(default=list, blank=True, help_text='Multiple choice only, e.g. ["-a", "-l"]')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label
```

Things worth noticing:

- **`related_name="tasks"`** lets you write `lab.tasks.all()` to get a lab's tasks. The
  serializers in step 5 use these names.
- **`on_delete=models.CASCADE`** means deleting a lab also deletes its tasks and their
  questions.
- **`order`** plus `Meta.ordering` keeps tasks in the order you choose, not the order they
  were created.
- **`options`** is a [`JSONField`](https://docs.djangoproject.com/en/5.2/ref/models/fields/):
  it stores a Python list (`["-h", "-a"]`) directly. It's only used for multiple-choice
  questions. A separate `Option` model would also work, but would be a fourth table for very
  little benefit.
- The sample data calls the question type `type`. Here it's **`kind`**, because `type` is a
  built-in Python name and it's best not to reuse it.

Create the tables:

```bash
python manage.py makemigrations labs
python manage.py migrate
```

### 3. Register the models in the admin

Replace `labs/admin.py`, so you can add and edit labs at `/admin/`:

```python
from django.contrib import admin

from .models import Lab, Question, Task


class TaskInline(admin.TabularInline):
    model = Task
    fields = ["order", "title"]
    show_change_link = True  # link to the full task page, where questions are edited
    extra = 0


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = ["title", "vmid", "order"]
    inlines = [TaskInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "lab", "order"]
    list_filter = ["lab"]
    inlines = [QuestionInline]
```

[Inlines](https://docs.djangoproject.com/en/5.2/ref/contrib/admin/) show related rows on the
same admin page: a lab's page lists its tasks, and a task's page lists its questions. The
task list on a lab's page only shows the order and title, with a link to the task's own page.
Editing long instructions and several questions all on one lab page would get crowded.

To use the admin you need a local admin account (README step 5):
`winpty python manage.py createsuperuser`.

### 4. Copy the sample data into the database

Rather than retyping the sample labs in the admin, this command copies them from
`sample_data.py`. It's a [custom management command](https://docs.djangoproject.com/en/5.2/howto/custom-management-commands/),
like `migrate` but your own. Create `labs/management/commands/load_sample_labs.py`. The
`management/commands/` folders and their `__init__.py` files already exist, because the HTTPS
`runserver` lives there.

```python
from django.core.management.base import BaseCommand

from labs.models import Lab
from labs.sample_data import LABS


class Command(BaseCommand):
    help = "Copy the hard-coded labs in labs/sample_data.py into the database."

    def handle(self, *args, **options):
        Lab.objects.all().delete()  # start fresh, so running it twice doesn't duplicate
        for lab_order, lab_data in enumerate(LABS):
            lab = Lab.objects.create(
                title=lab_data["title"],
                icon=lab_data["icon"],
                description=lab_data["description"],
                vmid=lab_data["vmid"],
                order=lab_order,
            )
            for task_order, task_data in enumerate(lab_data["tasks"]):
                task = lab.tasks.create(
                    title=task_data["title"],
                    instructions=task_data["instructions"],
                    order=task_order,
                )
                for q_order, q in enumerate(task_data["questions"]):
                    task.questions.create(
                        kind=q["type"],
                        label=q["label"],
                        options=q.get("options", []),
                        order=q_order,
                    )
        self.stdout.write(self.style.SUCCESS(f"Loaded {len(LABS)} labs."))
```

`enumerate` gives each item's position (0, 1, 2, ...), which becomes its `order`.
`lab.tasks.create(...)` uses the `related_name` from step 2 to make a task that already
belongs to this lab.

Run it:

```bash
python manage.py load_sample_labs
```

It should print `Loaded 2 labs.` **Careful:** it deletes all labs first, so only run it again
if you want to throw away changes made in the admin.

### 5. Write the serializers

Create `labs/serializers.py`. A [serializer](https://www.django-rest-framework.org/api-guide/serializers/)
lists which fields of a model go into the JSON. There are two for labs: a small one for the
sidebar and a full one for a single lab.

```python
from rest_framework import serializers

from .models import Lab, Question, Task


class LabListSerializer(serializers.ModelSerializer):
    """Just enough to draw the Labs sidebar."""

    task_count = serializers.IntegerField(read_only=True)  # added by .annotate() in the view

    class Meta:
        model = Lab
        fields = ["id", "title", "icon", "task_count"]


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "kind", "label", "options"]


class TaskSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = ["id", "title", "instructions", "questions"]


class LabDetailSerializer(serializers.ModelSerializer):
    """Everything about one lab, loaded when the student clicks it."""

    tasks = TaskSerializer(many=True, read_only=True)

    class Meta:
        model = Lab
        fields = ["id", "title", "description", "vmid", "tasks"]
```

- **`ModelSerializer`** reads the field types from the model, so you only list field names.
- **Nesting:** `tasks = TaskSerializer(many=True)` puts each lab's tasks *inside* the lab's
  JSON, and each task's questions inside the task
  ([nested relationships](https://www.django-rest-framework.org/api-guide/relations/)).
  `many=True` means "a list of them". `tasks` and `questions` must match the `related_name`s
  from the models. Because of the nesting, one request gets everything React needs for a lab,
  instead of one request per task.
- **`task_count`** isn't a model field. The view (next step) counts the tasks in the database
  query and adds it to each lab.
- Fields not listed, such as `order`, aren't sent. The API already returns things in order,
  so React doesn't need them. Leaving fields out is how the API stays small.

### 6. Write the API views and URLs

Create `labs/api_views.py`. DRF's [generic views](https://www.django-rest-framework.org/api-guide/generic-views/)
are class-based views that do almost everything; you only say which data and which
serializer to use.

```python
from django.db.models import Count
from rest_framework import generics

from .models import Lab
from .serializers import LabDetailSerializer, LabListSerializer


class LabListAPIView(generics.ListAPIView):
    """GET /api/labs/ -> the list of labs for the sidebar."""

    serializer_class = LabListSerializer
    queryset = Lab.objects.annotate(task_count=Count("tasks"))


class LabDetailAPIView(generics.RetrieveAPIView):
    """GET /api/labs/<id>/ -> one lab with its tasks and questions."""

    serializer_class = LabDetailSerializer
    queryset = Lab.objects.prefetch_related("tasks__questions")
```

- **`ListAPIView`** returns many objects; **`RetrieveAPIView`** returns one, by the `pk` in
  the URL (and a 404 if it doesn't exist). Both only allow `GET` (reading), so nobody can
  change labs through the API. Changes happen in the admin.
- **`annotate(task_count=Count("tasks"))`** makes the database count each lab's tasks as part
  of the same query.
- **`prefetch_related("tasks__questions")`** loads all of a lab's tasks and questions in two
  extra queries. Without it, Django would run one more query *for every task* to get its
  questions, which gets slow as labs grow. This is called the "N+1 queries" problem; Django's
  [database optimization](https://docs.djangoproject.com/en/5.2/topics/db/optimization/) page
  explains it.

The file is called `api_views.py` to keep it apart from the page views in `views.py`.

In `labs/urls.py`, import it and add two URLs:

```python
from django.urls import path

from . import api_views, views

urlpatterns = [
    path("", views.WorkspaceView.as_view(), name="workspace"),
    path("login/", views.ProxmoxLoginView.as_view(), name="login"),
    path("logout/", views.ProxmoxLogoutView.as_view(), name="logout"),
    path("proxmox/refresh/", views.RefreshTicketView.as_view(), name="refresh_ticket"),
    path("api/labs/", api_views.LabListAPIView.as_view(), name="api_lab_list"),
    path("api/labs/<int:pk>/", api_views.LabDetailAPIView.as_view(), name="api_lab_detail"),
]
```

`<int:pk>` captures the number in the URL (`/api/labs/2/` gives `pk=2`), and
`RetrieveAPIView` looks up the lab with that primary key.

### 7. Try the API in your browser

Start the server (`python manage.py runserver labs.example.com:8000`), log in to the site as
usual, then open **https://labs.example.com:8000/api/labs/**.

You'll see DRF's [browsable API](https://www.django-rest-framework.org/topics/browsable-api/):
a web page showing the JSON. You should see:

```json
[
    {"id": 1, "title": "Linux Basics", "icon": "bi-terminal", "task_count": 3},
    {"id": 2, "title": "Networking Fundamentals", "icon": "bi-diagram-3", "task_count": 2}
]
```

Then try **/api/labs/1/** to see one lab with its tasks and questions.

If you see `"Authentication credentials were not provided."`, you aren't logged in. Log in
on the site's normal login page first. That's the `IsAuthenticated` setting from step 1
working.

**Don't continue until both URLs work.**

## Part 2: The React app (Vite)

### 8. Install Node.js

1. Download the **LTS** ("long-term support") version from [nodejs.org](https://nodejs.org/)
   and run the installer with the default options.
2. **Close Git Bash and open it again** (and restart VS Code if you use its terminal), so it
   finds the new programs. A terminal only learns about newly installed programs when it
   starts.
3. Check it worked:

   ```bash
   node --version
   npm --version
   ```

   Both should print a version number. If you get `command not found`, close *every* Git
   Bash and VS Code window and try again.

Remember from *The big picture*: you only use Node.js on your own computer to build the
React code. Django still runs the website.

### 9. Create the `frontend` folder

The React source code lives in its own folder, `frontend/`, next to `manage.py`:

```
proxmox_lab_demo/
    django_project/
    labs/
    frontend/            <- new
        package.json
        vite.config.js
        src/
            main.jsx
            ...
    manage.py
```

**Why a separate folder?** It keeps the JavaScript tools (`package.json`, `node_modules/`)
apart from the Django code, the same way `.venv/` keeps Python packages apart. Django never
looks inside `frontend/`; it only sees the one file Vite builds into `labs/static/`.

Create the folders:

```bash
mkdir -p frontend/src
cd frontend
```

**Every `npm` command must be run inside `frontend/`**, because that's where `package.json` is.

**Why not `npm create vite@latest` like the tutorials?** That command makes a project for the
"React runs everything" architecture: an `index.html`, a dev server setup, example CSS and
components, and more. You'd delete most of it and change the rest. Writing two small files by
hand is quicker, and you'll understand every line.

Create `frontend/package.json` in your editor:

```json
{
  "name": "lab-workspace-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "vite build",
    "watch": "vite build --watch"
  },
  "dependencies": {
    "react": "^19.3.1",
    "react-dom": "^19.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^6.3.0",
    "vite": "^8.3.8"
  }
}
```

- **`"private": true`** stops this from ever being published to npm by accident.
- **`"type": "module"`** tells Node.js these files use `import`/`export`
  ([JavaScript modules](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules)),
  which `vite.config.js` does.
- **`"scripts"`** are shortcuts: `npm run build` runs `vite build`, and `npm run watch` runs
  `vite build --watch`.

Now install the packages:

```bash
npm install react react-dom
npm install --save-dev vite @vitejs/plugin-react
```

- **`react`** is React itself; **`react-dom`** connects it to the web page.
- **`vite`** is the build tool; **`@vitejs/plugin-react`** teaches it to handle JSX.
- **`--save-dev`** marks packages only needed for *building*. They're tools, not part of the
  app the browser runs.

npm adds them to `package.json`, downloads everything into `node_modules/`, and creates
`package-lock.json`. The lock file records the exact version of every package installed, so
everyone who runs `npm install` gets the same ones
([more about it](https://docs.npmjs.com/cli/configuring-npm/package-lock-json)). **Commit it.**

Add these lines to the project's `.gitignore`:

```
# React: installed packages and the built file (rebuild with `npm run build`)
frontend/node_modules/
labs/static/labs/react/
```

The built file is left out of Git because it's generated from `frontend/src/`, like
`node_modules/` from `package.json`. Anyone who clones the project runs `npm install` and
`npm run build` in `frontend/` to make it.

### 10. Configure Vite

Vite usually builds a whole website starting from an `index.html`. Here Django makes the
page, so Vite only needs to build one JavaScript file and put it in Django's static folder.
Create `frontend/vite.config.js`:

```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // Put the built file where Django looks for static files.
    outDir: '../labs/static/labs/react',
    emptyOutDir: true,
    rolldownOptions: {
      // Start from our JavaScript file (not an index.html, because Django makes the page).
      input: 'src/main.jsx',
      // Always name the output workspace.js, so the Django template can find it.
      output: { entryFileNames: 'workspace.js' },
    },
  },
});
```

- **`plugins: [react()]`** lets Vite understand JSX.
- **`outDir`** is relative to `frontend/`, so `../labs/...` means "up one folder, then into
  `labs`". Django finds files in an app's `static/` folder automatically, so the template can
  load it as `{% static 'labs/react/workspace.js' %}`.
- **`emptyOutDir`** deletes the old build first. That's why the output gets a folder of its
  own: never put your own files in `labs/static/labs/react/`, because the next build deletes
  them.
- **`input`**: where Vite starts reading. It follows every `import` from `main.jsx` to find
  all the other files.
- **`entryFileNames`**: Vite normally adds a random code to the name (`index-a1b2c3.js`) that
  changes whenever the code changes. That forces browsers to download the new version instead
  of using an old saved copy. A fixed name keeps this simple (the template never has to
  change), but browsers may sometimes use an old copy; Part 4 shows the fix. Bigger projects
  keep the codes and use Vite's [backend integration](https://vite.dev/guide/backend-integration)
  to look up the current name.
- **`rolldownOptions`** is the name in Vite 8 and newer. If `npm install` gave you an older
  Vite, the same option is called `rollupOptions`. Check with `npx vite --version`. All the
  options are in Vite's [build options reference](https://vite.dev/config/build-options).

### 11. Write the React components

#### How the components fit together

The app is split into small components, one per part of the screen:

```
App                     loads the data and remembers which lab is selected
├── LabList             column 1: the Labs sidebar
├── TaskList            column 2: the selected lab's tasks
│   └── Question        one question (text box, text area or radio buttons)
└── VmPane              column 3: the VM console iframe
```

And here is how data moves between them:

```
                     Django page (vms-data JSON)
                               |
                          main.jsx
                               | vms
                               v
 /api/labs/  ------->  +---------------+  <------- /api/labs/<id>/
                       |      App      |
                       |  state: labs, selectedId, lab, done
                       +---------------+
       labs, selectedId  |     | lab, done    | vmid (from lab), vms
                         v     v              v
                    LabList  TaskList       VmPane
                         |     |
         onSelect(id) ---+     +--- onDone(taskId)
         (calls setSelectedId)     (calls markDone)
```

- **Data goes down** as props: `App` hands each column only what it needs.
- **Events go up** as callback functions: when a lab is clicked, `LabList` calls `onSelect`,
  which is `App`'s `setSelectedId`.
- **Only `App` talks to the API.** The columns just display what they're given.

Keeping shared data in the closest common parent is called
[lifting state up](https://react.dev/learn/sharing-state-between-components). `LabList`,
`TaskList` and `VmPane` all depend on which lab is selected, so that lives in `App`.

#### Things that may look different from tutorials

- **No CSS imports.** Tutorials often `import './App.css'`. Here the styles are in the Django
  template (they were already there), and the components use the same class names as the old
  HTML, so the page looks identical.
- **Class names joined with `+`**, like `'nav-link' + (selected ? ' active' : '')`. Bigger
  projects often use a small library such as `clsx` for this; plain JavaScript is enough here.
- **Fetching inside `useEffect`.** That's the standard way to learn it, and it's what the
  React docs show in [Synchronizing with Effects](https://react.dev/learn/synchronizing-with-effects).
  Larger apps often use a data-fetching library (such as TanStack Query) instead. Plain
  `useEffect` keeps everything visible.
- **JSX attribute names:** `className` instead of `class`, `htmlFor` instead of `for`, and
  `style` takes an object: `style={{ height: '6px' }}`.

Now the files. Each one is followed by a walk-through of its parts.

#### `frontend/src/main.jsx`: the starting point

```jsx
// main.jsx is the "entry point": the first file Vite reads (see vite.config.js).
// Vite follows every `import` from here to find all the other files to bundle.
import { createRoot } from 'react-dom/client';
import App from './App.jsx';

// Django already put the student's VMs into the page as JSON, inside
// <script id="vms-data" type="application/json"> (see workspace.html).
// We read that text and turn it back into a JavaScript object.
const vms = JSON.parse(document.getElementById('vms-data').textContent);

// Find the empty <div id="react-root"> that the Django template left for us,
// and let React draw the whole App inside it. React only controls what's inside
// this div; the navbar above it is still plain Django HTML.
createRoot(document.getElementById('react-root')).render(<App vms={vms} />);
```

In a tutorial project, `main.jsx` looks almost the same, but finds a `<div id="root">` in
Vite's own `index.html`. Here the div is in the Django template instead, and there's one
extra step: reading the VM list Django put in the page.

- **`document.getElementById('vms-data').textContent`** is the JSON text inside the
  `<script id="vms-data" type="application/json">` tag the template makes (Part 3). A
  `<script>` with that `type` holds data and doesn't run.
- **`JSON.parse`** turns that text into a JavaScript object.
- **[`createRoot(...).render(...)`](https://react.dev/reference/react-dom/client/createRoot)**
  tells React to take over the `react-root` div and draw `<App>` inside it. The VM list is
  passed in as a prop.

#### `frontend/src/api.js`: one helper for API requests

```js
// A small helper so every component fetches from the API the same way.
//
// `url` is just a path like '/api/labs/'. No 'https://labs.example.com:8000' in front
// is needed, because this code runs on a page from that same site.
//
// The browser automatically sends the Django login cookie with the request,
// so the API knows which student is asking (no tokens needed).
export async function getJSON(url) {
  // Ask for JSON; otherwise DRF may send its HTML "browsable API" page.
  const response = await fetch(url, { headers: { Accept: 'application/json' } });

  // fetch() only throws if the network fails. A 403 or 404 is still a "successful"
  // response to fetch, so check the status ourselves and turn it into an error.
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} from ${url}`);
  }

  // Turn the JSON text in the response into JavaScript objects and arrays.
  return response.json();
}
```

- **[`fetch`](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch)** is the
  browser's built-in way to make HTTP requests. `await` waits for the answer.
- **Just a path, no server name:** tutorials write `fetch('http://localhost:8000/api/...')`
  because their API is on another server. Here it's the same site, so a path is enough, and
  it keeps working when the site's name changes.
- **`response.ok`** is true for status codes 200–299. Without this check, a 403 page would be
  passed on as if it were data.
- It's in its own file so every component fetches the same way, and there's one place to
  change it later (for example to add the CSRF header for `POST` requests).

#### `frontend/src/App.jsx`: loads the data

```jsx
import { useEffect, useState } from 'react';
import { getJSON } from './api.js';
import LabList from './LabList.jsx';
import TaskList from './TaskList.jsx';
import VmPane from './VmPane.jsx';

// App is the top component. It owns the data that more than one column needs,
// loads it from the API, and passes pieces of it down to the three columns as props.
// `vms` comes from main.jsx (Django put it in the page).
export default function App({ vms }) {
  // ---- State ----
  const [labs, setLabs] = useState([]);               // short list for the sidebar
  const [selectedId, setSelectedId] = useState(null); // id of the lab the student clicked
  const [lab, setLab] = useState(null);               // full details of that lab (null = loading)
  const [done, setDone] = useState({});               // finished tasks, e.g. { 1: true, 4: true }
  const [error, setError] = useState(null);           // message to show if a request fails

  // ---- Effect 1: once, when the page loads, get the list of labs ----
  // The empty [] at the end means "don't run this again after the first time".
  useEffect(() => {
    getJSON('/api/labs/')
      .then((data) => {
        setLabs(data);
        if (data.length > 0) setSelectedId(data[0].id); // start on the first lab
      })
      .catch((err) => setError(err.message));
  }, []);

  // ---- Effect 2: every time selectedId changes, get that lab's tasks ----
  // [selectedId] at the end means "run again whenever selectedId changes".
  // Clicking a lab only changes selectedId; this effect then does the loading.
  useEffect(() => {
    if (selectedId === null) return; // nothing selected yet (the lab list is still loading)

    let ignore = false; // becomes true if the student picks another lab before this one arrives
    setLab(null);       // TaskList shows "Loading..." while lab is null

    getJSON(`/api/labs/${selectedId}/`)
      .then((data) => {
        if (!ignore) setLab(data); // only show it if it's still the lab the student wants
      })
      .catch((err) => setError(err.message));

    // Cleanup: React runs this just before running the effect again for a new
    // selectedId, so the old request's answer gets ignored when it arrives.
    return () => {
      ignore = true;
    };
  }, [selectedId]);

  // Called by TaskList when a task's answers are submitted.
  // State must be replaced, not changed in place, so make a new object
  // with everything in `done` plus this task.
  function markDone(taskId) {
    setDone({ ...done, [taskId]: true });
  }

  // ---- What to draw ----
  if (error) {
    return <div className="alert alert-danger m-3">Couldn't load the labs: {error}</div>;
  }

  // <> ... </> is a "fragment": it groups the three columns without adding an extra <div>,
  // because the page's CSS expects them directly inside <div id="react-root" class="workspace">.
  return (
    <>
      <LabList labs={labs} selectedId={selectedId} onSelect={setSelectedId} />
      {/* key: a different lab gets a brand-new TaskList, so its first task opens */}
      <TaskList key={selectedId} lab={lab} done={done} onDone={markDone} />
      {/* lab?.vmid is undefined while the lab is loading (lab is null) */}
      <VmPane vmid={lab?.vmid} vms={vms} />
    </>
  );
}
```

How it works, part by part:

1. **The state.** `labs` is the sidebar list. `selectedId` is just a number. `lab` holds the
   full details of the selected lab, and is `null` while they load. `done` remembers finished
   tasks by task id, like `{ 1: true, 4: true }`. `error` holds a message if a request fails.
2. **Effect 1** has an empty dependency list `[]`, so it runs only once, after `App` first
   appears. It gets the lab list and selects the first lab.
3. **Effect 2** depends on `[selectedId]`, so it runs every time `selectedId` changes, including
   when Effect 1 sets it the first time. **This is how clicking a lab loads it:** the click
   only calls `setSelectedId`, and this effect reacts to the change. Clicking doesn't fetch
   anything directly. The effect sets `lab` to `null` first, so `TaskList` shows "Loading...".
4. **The `ignore` flag** handles fast clicking. If the student clicks lab 1 and then lab 2
   before lab 1's data arrives, React runs the cleanup function (`return () => { ignore = true }`)
   for lab 1 before starting lab 2. When lab 1's late answer arrives, it's ignored, so lab 2
   stays on screen. Without it, whichever request finished *last* would win, even if it was
   for the wrong lab. The React docs explain this in
   [Fetching data with Effects](https://react.dev/reference/react/useEffect).
5. **`markDone`** uses `{ ...done, [taskId]: true }`: a *new* object with everything in `done`
   ([spread syntax](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Spread_syntax))
   plus this task. React only notices a change if state gets a new object, not if the old one
   is changed in place ([updating objects in state](https://react.dev/learn/updating-objects-in-state)).
   `done` lives in `App`, not `TaskList`, so progress isn't lost when the student switches
   labs and comes back. Task ids are unique across all labs, so one object works for every lab.
6. **The error message** replaces everything if a request fails, so the student sees what
   went wrong instead of an empty page.
7. **The return.** The three columns are wrapped in `<>...</>`, a
   [Fragment](https://react.dev/reference/react/Fragment), because the page's CSS expects
   them directly inside the `workspace` div, with no extra wrapper.
   - **`key={selectedId}`** on `TaskList`: when a component's key changes, React throws the
     old one away and makes a new one, which resets its state. That's how "which task is open"
     goes back to the first task for each new lab
     ([resetting state with a key](https://react.dev/learn/preserving-and-resetting-state)).
   - **`lab?.vmid`** uses [optional chaining](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Optional_chaining):
     it gives `undefined` instead of crashing while `lab` is still `null`.

#### `frontend/src/LabList.jsx`: column 1

```jsx
import { useEffect, useState } from 'react';

// Column 1: the list of labs. It doesn't load anything itself. App gives it:
//   labs        the list from /api/labs/
//   selectedId  which lab to highlight
//   onSelect    a function to call when a lab is clicked (App's setSelectedId)
export default function LabList({ labs, selectedId, onSelect }) {
  // Is the sidebar collapsed to a strip of icons? The starting value is read from
  // localStorage (the browser's small per-site storage), so it's remembered between visits.
  // Passing a function to useState means it's only read once, not on every render.
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('labsCollapsed') === '1');

  // The page's CSS shrinks the sidebar when <body> has the class "labs-collapsed".
  // <body> is outside React's <div>, so React can't set that class through JSX.
  // An effect is the React way to update things outside React: it runs after
  // every render where `collapsed` changed.
  useEffect(() => {
    document.body.classList.toggle('labs-collapsed', collapsed);
    localStorage.setItem('labsCollapsed', collapsed ? '1' : '0');
  }, [collapsed]);

  return (
    <aside className="labs-sidebar bg-dark text-light p-3 border-end border-secondary">
      {/* Heading and the collapse button */}
      <div className="labs-header d-flex align-items-center justify-content-between mb-3">
        <h6 className="labs-heading text-uppercase text-secondary small fw-bold mb-0">Labs</h6>
        <button
          className="btn btn-sm btn-link text-secondary p-0"
          id="toggleLabs"
          title="Collapse/expand labs"
          onClick={() => setCollapsed(!collapsed)}
        >
          <i className="bi bi-chevron-double-left"></i>
        </button>
      </div>

      {/* One <li> per lab. React needs a unique `key` on each item of a list. */}
      <ul className="nav flex-column flex-nowrap gap-1">
        {labs.map((lab) => (
          <li className="nav-item" key={lab.id}>
            <a
              href="#"
              title={lab.title}
              // Bootstrap highlights the link that has the "active" class
              className={'nav-link d-flex align-items-center gap-2' + (lab.id === selectedId ? ' active' : '')}
              onClick={(event) => {
                event.preventDefault(); // don't follow href="#" (it would jump to the top)
                onSelect(lab.id);       // tell App which lab was clicked
              }}
            >
              <i className={'bi ' + lab.icon}></i>
              <span className="lab-label flex-grow-1">{lab.title}</span>
              <span className="badge rounded-pill text-bg-secondary">{lab.task_count}</span>
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
```

How it works:

1. **Props only, no fetching.** `LabList` draws what `App` gives it, and reports clicks with
   `onSelect`. It doesn't know about the API at all.
2. **The `collapsed` state** starts from [`localStorage`](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage),
   the browser's small storage for each site, so the choice is remembered after a reload.
   Passing a function to `useState` (`useState(() => ...)`) means it's only read on the first
   render.
3. **The effect updates `<body>`.** The CSS that shrinks the sidebar (and widens the tasks
   column) is written for `body.labs-collapsed`. `<body>` is outside React's div, so JSX can't
   set its class. Updating something outside React is exactly what effects are for.
4. **The list** uses `labs.map(...)` to make one `<li>` per lab. Each needs a unique
   [`key`](https://react.dev/learn/rendering-lists) so React can tell them apart; the
   database id is perfect.
5. **`event.preventDefault()`** stops the link from following `href="#"`, which would jump to
   the top of the page. The link is an `<a>` only because that's what Bootstrap's styles
   expect.

#### `frontend/src/TaskList.jsx`: column 2

```jsx
import { useState } from 'react';
import Question from './Question.jsx';

// Column 2: the selected lab's tasks, as an accordion (one task open at a time).
// App gives it:
//   lab     the lab from /api/labs/<id>/, or null while it's loading
//   done    which tasks are finished, e.g. { 1: true }
//   onDone  a function to call when a task's answers are submitted
export default function TaskList({ lab, done, onDone }) {
  // Which task is expanded: 0 = the first one, -1 = none.
  // (Hooks like useState must come before any early `return` below.)
  const [openIndex, setOpenIndex] = useState(0);

  // ---- Still loading ----
  if (lab === null) {
    return (
      <section className="tasks-sidebar bg-body-tertiary border-end">
        <div className="p-3 text-body-secondary small">Loading...</div>
      </section>
    );
  }

  // ---- Progress bar numbers, worked out from the props on every render ----
  const doneCount = lab.tasks.filter((task) => done[task.id]).length;
  const percent = lab.tasks.length > 0 ? (doneCount / lab.tasks.length) * 100 : 0;

  // ---- When a task's form is submitted ----
  function handleSubmit(event, task, index) {
    event.preventDefault(); // stop the browser's normal form submit, which would reload the page

    // Read every input in this form by its `name`, e.g. { q1: "/home/student", q2: "-a" }
    const answers = Object.fromEntries(new FormData(event.target));
    console.log('Answers for task', task.id, answers); // TODO: send to Django (see REACT_GUIDE.md)

    onDone(task.id);         // tell App this task is finished
    setOpenIndex(index + 1); // open the next task
  }

  return (
    <section className="tasks-sidebar bg-body-tertiary border-end">
      {/* ---- Header: lab title, description, progress bar ---- */}
      <div className="p-3 border-bottom bg-body">
        <h5 className="mb-1">{lab.title}</h5>
        <p className="text-body-secondary small mb-2">{lab.description}</p>
        <div className="d-flex align-items-center gap-2">
          {/* In JSX, `style` takes a JavaScript object, hence the double braces */}
          <div className="progress flex-grow-1" style={{ height: '6px' }}>
            <div className="progress-bar" style={{ width: `${percent}%` }}></div>
          </div>
          <small className="text-body-secondary">
            {doneCount}/{lab.tasks.length}
          </small>
        </div>
      </div>

      {/* ---- The tasks ---- */}
      <div className="tasks-body p-3">
        {/* `condition && <jsx>` only draws the JSX when the condition is true */}
        {lab.tasks.length === 0 && (
          <div className="text-body-secondary small text-center py-5">No tasks defined for this lab yet.</div>
        )}

        <div className="accordion">
          {lab.tasks.map((task, index) => {
            const isOpen = index === openIndex;
            return (
              <div className="accordion-item" key={task.id}>
                {/* Clickable task header: opens this task, or closes it if it's already open */}
                <h2 className="accordion-header">
                  <button
                    type="button"
                    className={'accordion-button py-2' + (isOpen ? '' : ' collapsed')}
                    onClick={() => setOpenIndex(isOpen ? -1 : index)}
                  >
                    <span className="task-status me-2">
                      {/* Green check if finished, empty circle if not */}
                      {done[task.id] ? (
                        <i className="bi bi-check-circle-fill text-success"></i>
                      ) : (
                        <i className="bi bi-circle text-body-tertiary"></i>
                      )}
                    </span>
                    <span className="small fw-semibold">
                      Task {index + 1}: {task.title}
                    </span>
                  </button>
                </h2>

                {/* Task body. Closed tasks are hidden with Bootstrap's "collapse" CSS
                    class instead of being removed, so typed answers aren't lost. */}
                <div className={'accordion-collapse collapse' + (isOpen ? ' show' : '')}>
                  <div className="accordion-body small">
                    <h6 className="text-uppercase text-body-secondary small fw-bold">Instructions</h6>
                    {/* The instructions are HTML written by the instructor in the Django admin.
                        This shows them as HTML instead of as text (see the guide). */}
                    <div dangerouslySetInnerHTML={{ __html: task.instructions }} />
                    <hr />
                    <h6 className="text-uppercase text-body-secondary small fw-bold">Questions</h6>
                    <form onSubmit={(event) => handleSubmit(event, task, index)}>
                      {task.questions.map((question) => (
                        <Question key={question.id} question={question} />
                      ))}
                      <div className="d-flex justify-content-end">
                        <button type="submit" className="btn btn-sm btn-primary">
                          {done[task.id] ? 'Update answers' : 'Submit'}
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
```

How it works:

1. **`openIndex`** remembers which task is expanded (`-1` means none). Hooks must be called
   before any early `return`, so it comes first.
2. **While loading** (`lab === null`), it shows "Loading..." and stops there.
3. **Progress** (`doneCount`, `percent`) is calculated on every render from `lab` and `done`.
   It isn't stored in state, because it can always be worked out from data React already has.
4. **`handleSubmit`** runs when a task's form is submitted:
   - `event.preventDefault()` stops the browser's normal form submission, which would reload
     the page.
   - [`new FormData(event.target)`](https://developer.mozilla.org/en-US/docs/Web/API/FormData)
     reads every input in the form by its `name`, and `Object.fromEntries` turns that into a
     plain object like `{ q1: "/home/student", q2: "-a" }`.
   - It logs the answers (they aren't saved yet; see *Where to go next*), tells `App` the task
     is done, and opens the next task.
5. **The header** shows the lab's title, description and progress bar.
6. **The accordion** draws every task. Each task's header button sets `openIndex`, and its
   body gets Bootstrap's `collapse show` classes when open
   ([Bootstrap accordion](https://getbootstrap.com/docs/5.3/components/accordion/)).

Three choices here differ from what you might expect:

- **React opens and closes the tasks, not Bootstrap's JavaScript.** The old page used
  Bootstrap's own JavaScript for the accordion. If Bootstrap's script and React both changed
  the same HTML, React wouldn't know about Bootstrap's changes and would undo them on its next
  render. So React controls everything with `openIndex`, and only Bootstrap's *CSS* is used.
  That's also why Part 3 removes Bootstrap's script from the template.
- **Closed tasks stay on the page, hidden by CSS.** A common tutorial pattern is
  `{isOpen && <div>...</div>}`, which removes the closed task from the page. Here that would
  delete anything the student had typed into it. Hiding it keeps the answers.
- **The inputs are "uncontrolled".** Tutorials usually make every input "controlled": a
  `useState` for each one, with `value` and `onChange`. That's useful when React needs each
  value *while* the student types (to check it live, for example). Here the answers are only
  needed when the form is submitted, and questions come from the database, so there would be
  an unknown number of state variables. Reading them all with `FormData` on submit is much
  simpler. The React docs cover both ways under
  [`<input>`](https://react.dev/reference/react-dom/components/input).

**About `dangerouslySetInnerHTML`:** normally React shows text as text: if the instructions
contain `<code>ls</code>`, the student would literally see the tags. Setting
[`dangerouslySetInnerHTML`](https://react.dev/reference/react-dom/components/common) shows it
as HTML instead. The scary name is on purpose: if the HTML came from a user, they could put a
`<script>` in it and run code in other people's browsers (an
[XSS attack](https://owasp.org/www-community/attacks/xss/)). It's safe here only because the
instructions are written by the instructor in the admin. **Never use it on anything a student
typed.**

#### `frontend/src/Question.jsx`: one question

```jsx
// One question inside a task's form. The `kind` from the API decides which input to draw:
//   "text"      one-line text box
//   "textarea"  multi-line text box
//   "radio"     multiple choice, one radio button per option
export default function Question({ question }) {
  // Every input is named after the question's database id: q1, q2, ...
  // TaskList's handleSubmit reads the answers by these names.
  const name = `q${question.id}`;

  // The label is the same for every kind, so build it once.
  // It may contain HTML such as <code>, written by the instructor in the Django admin.
  const label = (
    <label
      className="form-label small fw-semibold"
      htmlFor={name} // JSX spells the HTML "for" attribute as htmlFor
      dangerouslySetInnerHTML={{ __html: question.label }}
    />
  );

  if (question.kind === 'textarea') {
    return (
      <div className="mb-3">
        {label}
        <textarea className="form-control form-control-sm" rows={3} id={name} name={name} />
      </div>
    );
  }

  if (question.kind === 'radio') {
    return (
      <div className="mb-3">
        {label}
        {/* All radio buttons share the same `name`, so only one can be picked.
            Each needs its own `id` so clicking its label selects it. */}
        {question.options.map((option, i) => (
          <div className="form-check" key={option}>
            <input className="form-check-input" type="radio" name={name} id={`${name}-${i}`} value={option} />
            <label className="form-check-label small" htmlFor={`${name}-${i}`}>
              {option}
            </label>
          </div>
        ))}
      </div>
    );
  }

  // "text" (and any kind we don't recognize): a one-line answer
  return (
    <div className="mb-3">
      {label}
      <input type="text" className="form-control form-control-sm" id={name} name={name} />
    </div>
  );
}
```

How it works:

- **One component, three kinds.** It checks `question.kind` and returns a different input for
  each. Returning early from each `if` keeps each case easy to read.
- **The `name`** is `q` + the question's database id (`q1`, `q2`, ...). That's what
  `TaskList`'s `FormData` uses as the key, so when answers are saved later, Django can tell
  exactly which question each one belongs to.
- **The label is built once** and reused, since all three kinds share it. It uses
  `dangerouslySetInnerHTML` for the same reason as the instructions.
- **Radio buttons** all share one `name` (that's how the browser knows only one can be picked),
  but each needs its own `id` so that clicking its text selects it.

#### `frontend/src/VmPane.jsx`: column 3

```jsx
import { useRef, useState } from 'react';

// Column 3: the VM console. App gives it:
//   vmid  the selected lab's VM id (from the API), or undefined while the lab is loading
//   vms   every VM this student may use, from Django, e.g. { "100": { name, node, status, console_url } }
export default function VmPane({ vmid, vms }) {
  const [reloads, setReloads] = useState(0); // add 1 to reconnect the console (see the iframe's key)
  const frameWrap = useRef(null);            // the real <div> around the iframe, for fullscreen

  // Look up this lab's VM. It's undefined while loading, or if the student's
  // Proxmox account doesn't have access to that VM.
  const vm = vms[vmid];

  // ---- Status badge text and color ----
  let status = 'loading';
  if (vmid !== undefined) status = vm ? vm.status : 'not available';

  let badgeColor = 'text-bg-warning';                        // yellow: loading / not available
  if (status === 'running') badgeColor = 'text-bg-success';  // green
  else if (vm) badgeColor = 'text-bg-secondary';             // gray: e.g. "stopped"

  return (
    <main className="vm-pane">
      {/* ---- Toolbar: status, VM name, buttons ---- */}
      <div className="d-flex align-items-center gap-2 px-3 py-2 bg-body border-bottom">
        <span className={'badge ' + badgeColor}>{status}</span>
        <span className="fw-semibold small">
          {vm ? `${vm.name} (VM ${vm.vmid} on ${vm.node})` : vmid !== undefined && `VM ${vmid}`}
        </span>
        <div className="ms-auto btn-group btn-group-sm">
          {/* Reconnect: changing `reloads` changes the iframe's key below */}
          <button
            className="btn btn-outline-secondary"
            title="Reconnect"
            disabled={!vm}
            onClick={() => setReloads(reloads + 1)}
          >
            <i className="bi bi-arrow-clockwise"></i>
          </button>
          {/* Open the console in its own browser tab */}
          <a
            className={'btn btn-outline-secondary' + (vm ? '' : ' disabled')}
            href={vm?.console_url}
            target="_blank"
            rel="noopener"
            title="Open console in a new tab"
          >
            <i className="bi bi-box-arrow-up-right"></i>
          </a>
          {/* Fullscreen: needs the real DOM element, which the ref gives us */}
          <button
            className="btn btn-outline-secondary"
            title="Fullscreen"
            onClick={() => frameWrap.current.requestFullscreen()}
          >
            <i className="bi bi-arrows-fullscreen"></i>
          </button>
        </div>
      </div>

      {/* ---- The console itself, or a message ---- */}
      {/* ref={frameWrap} makes frameWrap.current point at this <div> once it's on the page */}
      <div className="vm-frame-wrap" ref={frameWrap}>
        {vm ? (
          // THIS is what shows the VM: the iframe loads the Proxmox console page.
          // The browser sends the PVEAuthCookie Django set, so the console is logged in.
          // A new key makes React replace the iframe, which reloads the console.
          <iframe
            key={`${vm.vmid}-${reloads}`}
            src={vm.console_url}
            title="Virtual machine console"
            allow="clipboard-read; clipboard-write; fullscreen"
          />
        ) : (
          <div className="vm-placeholder">
            <i className="bi bi-display fs-1 mb-2"></i>
            {vmid === undefined ? (
              <div>Loading...</div>
            ) : (
              <>
                <div>VM {vmid} isn't available to your Proxmox account.</div>
                <small>VMs you can access: {Object.keys(vms).join(', ') || 'none'}</small>
              </>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
```

How it works:

1. **Finding the VM.** `vms[vmid]` looks up the lab's VM in the list Django provided. `vms`
   came from JSON, where object keys are always strings (`"100"`), but JavaScript converts the
   number `100` to `"100"` when looking up a key, so it still works. It's `undefined` while the
   lab loads (`vmid` is `undefined`) or when the student's account can't use that VM.
2. **The badge** text and color are worked out from those two cases with plain `if`s.
3. **The toolbar buttons:**
   - **Reconnect** adds 1 to `reloads`, which changes the iframe's `key`. React then removes
     the old iframe and adds a new one, which loads the console again. (That's the same "new
     key, new component" idea used for `TaskList`.)
   - **Open in a new tab** is an ordinary link to the console URL.
   - **Fullscreen** calls the browser's [`requestFullscreen()`](https://developer.mozilla.org/en-US/docs/Web/API/Element/requestFullscreen)
     on the `<div>` around the iframe. That needs the real page element, not React's
     description of it, which is what [`useRef`](https://react.dev/reference/react/useRef)
     provides: after React puts the `<div ref={frameWrap}>` on the page, `frameWrap.current`
     is that element.
4. **The iframe.** This is the line that shows the VM. Its `src` is the console URL Django
   built. Logging in to the console still works exactly as the README describes: the browser
   sends the `PVEAuthCookie` that Django set, and React doesn't need to know about it.
5. **Otherwise, a message:** "Loading..." or "VM 101 isn't available to your Proxmox account",
   with the VMs the student *can* use.

### 12. Build it

From inside `frontend/`:

```bash
npm run build
```

Vite prints the file it wrote (`../labs/static/labs/react/workspace.js`) and its size, then
`built in ...`. Check the file exists: `ls ../labs/static/labs/react/` should show
`workspace.js`. That one file contains your components *and* React itself, which is why it's
around 200 kB. This is the "bundle": the browser downloads one file instead of dozens.

Go back to the project folder for the next part: `cd ..`

## Part 3: Connect React to the Django page

### 13. Change the template

Open `labs/templates/labs/workspace.html`.

**a)** Add this as the very first line, above `<!doctype html>`, so the template can use
`{% static %}`:

```django
{% load static %}
```

**b)** Keep everything from the top down to the end of the `{% if vm_error %}...{% endif %}`
block, including all the CSS in `<style>`: React uses the same class names, so the page looks
the same.

**c)** Replace **everything after** `{% endif %}`, from `<div class="workspace">` to the end
of the file, with:

```django
  <!-- React draws the Labs, Tasks and VM columns inside this div.
       Its code is in frontend/src/, built into labs/static/labs/react/workspace.js. -->
  <div class="workspace" id="react-root"></div>

  <!-- Data only Django can provide (it needs the Proxmox ticket). React reads it in main.jsx. -->
  {{ vms|json_script:"vms-data" }}
  {% csrf_token %}

  <script>
    // Plain JavaScript for the parts of the page Django draws (not React).

    // Navbar button: hide both sidebars to give the VM the full width.
    document.getElementById('togglePanels').addEventListener('click', () => {
      document.body.classList.toggle('panels-hidden');
    });

    // Keep the Proxmox ticket alive: every 10 minutes ask Django for a fresh one.
    // The response sets a new PVEAuthCookie, so the console iframe stays logged in.
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    setInterval(async () => {
      const r = await fetch("{% url 'refresh_ticket' %}", {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
      });
      if (r.status === 401) window.location = "{% url 'login' %}";
    }, 10 * 60 * 1000);
  </script>

  <!-- The React app, built by Vite (cd frontend && npm run build). -->
  <script type="module" src="{% static 'labs/react/workspace.js' %}"></script>
</body>
</html>
```

What changed and why:

- **The three columns are gone from the HTML.** React draws them inside `<div id="react-root">`.
  The div keeps the `workspace` class, because the CSS lays out the three columns with it.
- **`labs-data` is gone.** The labs now come from the API. **`vms-data` stays**, because only
  Django can get the VM list. Django's [`json_script`](https://docs.djangoproject.com/en/5.2/ref/templates/builtins/)
  filter writes it into the page as JSON safely, so data like a VM name can't break the HTML.
- **The ticket refresh stays in plain JavaScript.** It has nothing to do with labs and must
  keep running no matter what React is showing. It also uses `{% url %}`, which only works
  in a template: Django fills it in when it makes the page. Files Vite builds never go through
  Django's template engine, so template tags can't be used in them.
- **The hide-panels button stays in plain JavaScript** too, because the button is in the
  navbar, which Django draws, not React.
- **Bootstrap's JavaScript (`bootstrap.bundle.min.js`) is removed**, because React now
  opens and closes the tasks (see `TaskList.jsx`). Bootstrap's CSS link in `<head>` stays.
- **`type="module"`** is required: Vite builds a modern JavaScript module, and browsers only
  run those from a `<script type="module">`.
- **The React script is last**, after the `react-root` div and `vms-data`, so both exist
  by the time React looks for them. (Module scripts also wait for the page to finish loading.)

### 14. Stop sending the hard-coded labs

In `labs/views.py`:

1. Delete the line `from .sample_data import LABS`.
2. In `WorkspaceView.get_context_data`, delete the line `"labs": LABS,` from the
   `context.update({...})` call. Keep `"vms"`, `"vm_error"` and `"proxmox_username"`.

`sample_data.py` is now only used by `load_sample_labs`.

### 15. Try it

```bash
python manage.py runserver labs.example.com:8000
```

Open **https://labs.example.com:8000** and log in. The page should look exactly as before.
To check it's really React and the API:

- Press **F12 → Network**, then click a lab. You'll see a request to `/api/labs/2/`.
- Change a task's title in the admin (`/admin/`), reload the workspace, and see the new title.

## Part 4: Working on it day to day

You now have two kinds of code:

- **Python** (`.py` files and templates): `runserver` notices changes and reloads by itself.
- **React** (`frontend/src/`): the browser only ever loads the *built* `workspace.js`, so it
  must be rebuilt after every change.

So use **two terminals**:

| Terminal 1 (project folder) | Terminal 2 (`frontend/` folder) |
|---|---|
| `source .venv/Scripts/activate` | `cd frontend` |
| `python manage.py runserver labs.example.com:8000` | `npm run watch` |

`npm run watch` rebuilds `workspace.js` automatically every time you save a file in
`frontend/src/`. After saving, wait for `built in ...` in terminal 2, then reload the page in
the browser.

In VS Code, the **split terminal** button (next to **+** in the terminal panel) shows two
terminals side by side ([VS Code terminal basics](https://code.visualstudio.com/docs/terminal/basics)).
Stop either one with **Ctrl+C**.

**If a change doesn't show up**, the browser may be using a copy of `workspace.js` it saved
earlier ([HTTP caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)). Reload
with **Ctrl+F5** (or **Ctrl+Shift+R**) to make it download the file again. This is the
downside of the fixed file name chosen in step 10.

**How is this different from `npm run dev`?** In tutorials, `npm run dev` starts Vite's own
server, which updates the page the instant you save, without reloading ("hot module
replacement"). That needs the page to come from Vite. Here the page comes from Django, so we
just rebuild the file instead. Using Vite's dev server with a Django page is possible (see
*Where to go next*), but it's more setup than this project needs.

**After cloning the project, or pulling changes to `frontend/`:** run `npm install` and
`npm run build` in `frontend/` once, as well as the usual `pip install -r requirements.txt`
and `python manage.py migrate`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| The three columns are empty; only the navbar shows | The React app didn't load or crashed. Press F12 → *Console* for the error. If the Network tab shows `workspace.js` as **404**, it hasn't been built: run `npm run build` in `frontend/`. |
| `workspace.js` is 404 even though the file exists | Django only serves static files this way when `DEBUG=True` in `.env`. Also check `{% static 'labs/react/workspace.js' %}` matches the file's location under `labs/static/`. |
| Console: `Cannot use import statement outside a module` | The `<script>` tag for `workspace.js` is missing `type="module"`. |
| Red box: `Couldn't load the labs: 403 Forbidden from /api/labs/` | You're not logged in (or your session expired). Log in again. |
| Red box: `... 404 Not Found from /api/labs/...` | The API URLs aren't in `labs/urls.py`, or they're different from the paths in `App.jsx`. |
| Sidebar is empty, no error | The database has no labs. Run `python manage.py load_sample_labs`, or add one in the admin. |
| `no such table: labs_lab` | You didn't run `python manage.py makemigrations labs` and `python manage.py migrate`. |
| Changes to `.jsx` files don't show up | Is `npm run watch` running, and did it finish rebuilding? Then hard-reload the page with **Ctrl+F5** (or **Ctrl+Shift+R**) so the browser doesn't use an old copy of `workspace.js`. |
| A tutorial's code tries to fetch `http://localhost:8000/...` or mentions CORS | That's the other architecture (see *How this differs from a React tutorial*). Use plain paths like `/api/labs/`; no CORS setup is needed here. |
| `npm: command not found` | Node.js isn't installed, or Git Bash was opened before installing it. Close all Git Bash and VS Code windows and reopen them. |
| `npm ERR! enoent ... package.json` | You're in the wrong folder. `cd frontend` first. |
| Vite says it can't find `index.html` | Vite didn't use your config. Check the file is `frontend/vite.config.js` and contains `input: 'src/main.jsx'`. With a Vite older than 8, the option is `rollupOptions`, not `rolldownOptions`. |
| Tasks show raw tags like `<code>` | That text is being displayed as text. Use `dangerouslySetInnerHTML` (see `TaskList.jsx`), and only for HTML the instructor wrote. |
| The VM console stopped working | Not a React problem. Follow the README's Troubleshooting: the HTTPS and cookie rules are the same. |

## Where to go next

- **Save the answers.** Right now *Submit* only logs the answers to the browser console.
  To save them, add an `Answer` model (student, question, text), a DRF `CreateAPIView`, and
  `POST` the answers from `handleSubmit` with `fetch`. Unlike `GET`, a `POST` must include
  Django's [CSRF token](https://docs.djangoproject.com/en/5.2/howto/csrf/): read it from the
  page with `document.querySelector('[name=csrfmiddlewaretoken]').value` and send it in an
  `X-CSRFToken` header, exactly like the ticket refresh code in `workspace.html` does.
  Then load each student's saved answers and progress from the API, instead of starting
  empty on every page load.
- **Show each student only their labs.** Override `get_queryset()` in the API views to
  filter by `self.request.user`.
- **Instant updates while developing.** Vite's dev server can update the page as you save,
  without reloading, but using it with a Django-made page needs extra setup. Vite's
  [backend integration guide](https://vite.dev/guide/backend-integration) explains how, and
  the `django-vite` package does much of it for you.

## Further reading

**The architecture used here**
- React docs: [Add React to an existing project](https://react.dev/learn/add-react-to-an-existing-project).
  The section on using React for a part of an existing page is this project's approach.
- patterns.dev: [Islands architecture](https://www.patterns.dev/vanilla/islands-architecture/)
- Vite: [Backend integration](https://vite.dev/guide/backend-integration)

**Django REST Framework**
- [Quickstart tutorial](https://www.django-rest-framework.org/tutorial/quickstart/)
- [Serializers](https://www.django-rest-framework.org/api-guide/serializers/) and
  [nested relationships](https://www.django-rest-framework.org/api-guide/relations/)
- [Generic views](https://www.django-rest-framework.org/api-guide/generic-views/)
- [Authentication](https://www.django-rest-framework.org/api-guide/authentication/) and
  [permissions](https://www.django-rest-framework.org/api-guide/permissions/)

**React concepts used in the components**
- [Synchronizing with Effects](https://react.dev/learn/synchronizing-with-effects) and the
  [`useEffect` reference](https://react.dev/reference/react/useEffect) (includes fetching data)
- [Sharing state between components](https://react.dev/learn/sharing-state-between-components)
- [Preserving and resetting state](https://react.dev/learn/preserving-and-resetting-state) (the `key` trick)
- [Rendering lists](https://react.dev/learn/rendering-lists) and
  [conditional rendering](https://react.dev/learn/conditional-rendering)
- [Updating objects in state](https://react.dev/learn/updating-objects-in-state)
- [`useRef`](https://react.dev/reference/react/useRef)

**Tools**
- [Vite guide](https://vite.dev/guide/)
- [Introduction to Node.js](https://nodejs.org/en/learn/getting-started/introduction-to-nodejs)
- [About npm](https://docs.npmjs.com/about-npm)
- Django: [managing static files](https://docs.djangoproject.com/en/5.2/howto/static-files/)

**Browser features**
- MDN: [Using the Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch),
  [FormData](https://developer.mozilla.org/en-US/docs/Web/API/FormData),
  [JavaScript modules](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules),
  [CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)
