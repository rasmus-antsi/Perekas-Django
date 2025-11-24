#!/bin/bash
# Script to run migrations on production
# This should be run on your production server or via Railway CLI

echo "Running Django migrations..."
python manage.py migrate --noinput

echo "Checking migration status..."
python manage.py showmigrations a_family

echo "Done!"

