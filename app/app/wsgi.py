import os
import sys
from django.core.wsgi import get_wsgi_application

# Agregar el directorio raíz al path
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

application = get_wsgi_application()
app = application  # Esto es lo que Vercel necesita