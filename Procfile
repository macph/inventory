release: python manage.py migrate && python manage.py loaddata units.json preset_items.json
web: gunicorn server.wsgi --timeout 10
