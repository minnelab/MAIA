# MAIA Dashboard Integration Guide

The MAIA Django dashboard has been integrated into the `maia-toolkit` package, allowing you to deploy and manage the dashboard as part of your MAIA installation.

## Overview

The dashboard application includes:
- **Authentication system** for user management
- **GPU scheduling** for resource allocation
- **Namespace management** for organizing projects
- **User management interface**
- **Resource monitoring and management**
- **RESTful API** for programmatic access

## Installation

The dashboard is automatically installed when you install `maia-toolkit`:

```bash
pip install maia-toolkit
```

This will install all required Django dependencies including:
- Django
- djangorestframework
- django-allauth
- mozilla-django-oidc
- And other necessary packages

## Quick Start

To set up and run the dashboard:

```bash
MAIA_setup_dashboard
```

This command will:
1. Create migrations for the authentication app
2. Create migrations for the GPU scheduler app
3. Create general Django migrations
4. Apply all migrations to the database
5. Start the development server on `http://0.0.0.0:8000`

## Command Options

The `MAIA_setup_dashboard` command supports several options:

```bash
# Run on a specific host and port
MAIA_setup_dashboard --host 127.0.0.1 --port 8080

# Only run migrations without starting the server
MAIA_setup_dashboard --no-server

# Run the server in background mode
MAIA_setup_dashboard --background

# Combine options
MAIA_setup_dashboard --host 0.0.0.0 --port 8000 --background
```

### Options

- `--host HOST`: Bind address for the server (default: `0.0.0.0`)
- `--port PORT`: Port number for the server (default: `8000`)
- `--no-server`: Only run migrations, don't start the server
- `--background`: Run server in background (detached mode)

## Manual Setup

If you prefer to run the setup steps manually:

```bash
# Navigate to the dashboard directory
cd $(python -c "import MAIA.dashboard; import os; print(os.path.dirname(MAIA.dashboard.__file__))")

# Run migrations
python manage.py makemigrations authentication
python manage.py makemigrations gpu_scheduler
python manage.py makemigrations
python manage.py migrate

# Start the server
python manage.py runserver 0.0.0.0:8000 --insecure
```

## Production Deployment

For production use, consider:

1. **Using a production-grade web server** like Gunicorn or uWSGI:
   ```bash
   gunicorn core.wsgi:application --bind 0.0.0.0:8000
   ```

2. **Setting up a reverse proxy** with Nginx or Apache

3. **Configuring proper database settings** in Django settings

4. **Using environment variables** for sensitive configuration

5. **Collecting static files**:
   ```bash
   python manage.py collectstatic --noinput
   ```

## Dashboard Structure

The dashboard package is located at `MAIA.dashboard` and contains:

```
MAIA/dashboard/
├── apps/              # Django applications
│   ├── api/          # RESTful API
│   ├── authentication/  # User authentication
│   ├── gpu_scheduler/   # GPU scheduling
│   ├── namespaces/   # Namespace management
│   ├── user_management/ # User management
│   ├── resources/    # Resource management
│   ├── home/         # Home page views
│   ├── maia/         # Static assets
│   └── templates/    # HTML templates
├── core/             # Django core settings
│   ├── settings.py   # Django configuration
│   ├── urls.py       # URL routing
│   └── wsgi.py       # WSGI configuration
└── manage.py         # Django management script
```

## Configuration

The dashboard uses Django settings located at `MAIA/dashboard/core/settings.py`. You can customize:

- Database configuration
- Authentication backends
- Installed applications
- Middleware
- Static and media file handling
- Security settings

## Environment Variables

Common environment variables for the dashboard:

- `DJANGO_SECRET_KEY`: Secret key for Django (required in production)
- `DJANGO_DEBUG`: Debug mode (set to `False` in production)
- `DATABASE_URL`: Database connection string
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

## Accessing the Dashboard

Once the server is running:

1. Open your browser and navigate to `http://localhost:8000` (or your configured host/port)
2. You'll be presented with the MAIA dashboard login page
3. Use your credentials to access the dashboard features

## Features

### GPU Scheduling
Manage GPU resources and allocate them to different users and projects.

### User Management
Create, update, and manage user accounts and permissions.

### Namespace Management
Organize resources into namespaces for better project isolation.

### Resource Monitoring
Monitor and manage compute resources across your MAIA installation.

### RESTful API
Access dashboard functionality programmatically through the API endpoints.

## Troubleshooting

### Migration Issues

If you encounter migration errors:
```bash
# Reset migrations (development only!)
python manage.py migrate --fake-initial

# Or recreate the database
python manage.py flush
MAIA_setup_dashboard --no-server
```

### Static Files Not Loading

Ensure static files are collected:
```bash
cd $(python -c "import MAIA.dashboard; import os; print(os.path.dirname(MAIA.dashboard.__file__))")
python manage.py collectstatic --noinput
```

### Port Already in Use

If port 8000 is already in use:
```bash
MAIA_setup_dashboard --port 8080
```

## Development

For development work on the dashboard:

1. **Install in editable mode**:
   ```bash
   pip install -e .
   ```

2. **Run with debug mode**:
   ```bash
   # Edit core/settings.py to set DEBUG = True
   MAIA_setup_dashboard
   ```

3. **Create a superuser**:
   ```bash
   cd $(python -c "import MAIA.dashboard; import os; print(os.path.dirname(MAIA.dashboard.__file__))")
   python manage.py createsuperuser
   ```

## Support

For issues and questions:
- GitHub Issues: https://github.com/minnelab/MAIA/issues
- Documentation: https://maia-toolkit.readthedocs.io

## License

The MAIA dashboard is part of the maia-toolkit package and is licensed under GPLv3.
