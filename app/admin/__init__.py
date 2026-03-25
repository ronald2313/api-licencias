"""
Panel Administrativo para API de Licencias
Blueprint separado para gestión de licencias y configuración
"""
from flask import Blueprint

admin_bp = Blueprint('admin', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/admin')

from . import routes
