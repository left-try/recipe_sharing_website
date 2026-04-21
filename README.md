# Recipe Sharing Website

A full-stack recipe sharing web app with authentication, recipe CRUD, recipe image storage via an external file upload system, downloadable recipe PDFs, comments, likes, favorites, tags/categories and search.

## Features

- **Auth**: Register, login, logout, password reset
- **User Profiles**: Bio + avatar upload
- **Recipes**: Create, edit, delete, publish/unpublish, image and video upload
- **Discovery**: Search, filter by category/tag, sort by newest/popular, pagination
- **Community**: Comments, likes, favorites
- **Recipe PDF Export**: Download a single recipe as a PDF from the detail page
- **Permissions**: Only the recipe owner (or admin) can edit/delete; comment owner (or admin) can delete comment

## Tech Stack

- Backend: Python, Flask, SQLAlchemy, Flask-Login, Flask-WTF (CSRF)
- Integrations: HTTP-based file storage API for recipe visuals
- DB: SQLite
- Frontend: HTML, CSS, Vanilla JS (Fetch API)

## Setup Instructions

### 1) Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Environment variables

For recipe image uploads configure:

```bash
FILE_STORAGE_API_BASE_URL=https://your-storage-service.example.com
FILE_STORAGE_API_TOKEN=your-api-token
FILE_STORAGE_TIMEOUT_SECONDS=10
```

### 4) Initialize DB (tables + seed categories)

```bash
flask --app run.py init-db
```

Optional: create an admin user:

```bash
flask --app run.py create-admin
```

### 5) Run

```bash
flask --app run.py run
```

Open: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)

## Project Structure

```
recipe_sharing_website/
  app/
    __init__.py
    config.py
    extensions.py
    models.py
    utils.py
    auth/
      routes.py
      forms.py
    recipes/
      routes.py
      forms.py
    main/
      routes.py
    api/
      routes.py
    templates/
      base.html
      main/
      auth/
      recipes/
      errors/
    static/
      css/style.css
      js/main.js
      uploads/         (created at runtime)
      avatars/         (created at runtime)
  run.py
  requirements.txt
  README.md
  .env.example
```
## Notes

- Password reset is implemented with a timed token. For simplicity in a course project, the reset URL is printed in the server console. Later a real email provider could be connected.
- New recipe image uploads are sent to the external file storage service with `POST /files` and removed with `DELETE /files/<file_id>`.
- The storage service is expected to return a file identifier and a public URL in its upload response.
- Profile avatars use local storage under `app/static/avatars`.
- Each recipe detail page includes a PDF export download.
- SQLite file is `app.db` by default.


## Demo
[https://drive.google.com/file/d/100pIDnXUU1yXbj9KR1n30Z6w3TSn4BF6/view?usp=sharing](https://drive.google.com/file/d/100pIDnXUU1yXbj9KR1n30Z6w3TSn4BF6/view?usp=sharing)
## Feedback from the professor
[https://drive.google.com/file/d/1_jGbEePVKlUat7d-wNJWcbABZyrJ22O1/view?usp=sharing](https://drive.google.com/file/d/1_jGbEePVKlUat7d-wNJWcbABZyrJ22O1/view?usp=sharing)
