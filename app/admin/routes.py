from flask import jsonify, request

from app.models import License, BusinessConfig


def register_routes(app):

    @app.route("/", methods=["GET"])
    def home():
        return jsonify({
            "status": "ok",
            "message": "API de licencias funcionando"
        }), 200

    @app.route("/api/v1/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/api/v1/validate", methods=["GET"])
    def validate_license():
        license_key = request.args.get("license_key")

        if not license_key:
            return jsonify({"error": "license_key requerido"}), 400

        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            return jsonify({
                "valid": False,
                "message": "Licencia no encontrada"
            }), 404

        license_obj.actualizar_estado()

        return jsonify({
            "valid": license_obj.esta_activa,
            "estado": license_obj.estado,
            "dias_restantes": license_obj.dias_restantes,
            "message": "Licencia válida" if license_obj.esta_activa else "Licencia no válida"
        }), 200

    @app.route("/api/v1/business-config", methods=["GET"])
    def business_config():
        license_key = request.args.get("license_key")

        if not license_key:
            return jsonify({"error": "license_key requerido"}), 400

        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            return jsonify({"error": "Licencia no encontrada"}), 404

        config = BusinessConfig.query.filter_by(
            customer_id=license_obj.customer_id
        ).first()

        if not config:
            return jsonify({
                "status": "ok",
                "business_name": "",
                "rnc": "",
                "phone": "",
                "address": ""
            }), 200

        return jsonify({
            "status": "ok",
            "business_name": getattr(config, "nombre_negocio", ""),
            "rnc": getattr(config, "rnc_cedula", ""),
            "phone": getattr(config, "telefono", ""),
            "address": getattr(config, "direccion", "")
        }), 200