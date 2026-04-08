import json
import io
import base64
import pandas as pd
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .utils import (
    parse_reporte,
    parse_trabajadores,
    build_cruce_preview,
    build_emp_preview,
    generate_infra,
)


def index(request):
    """
    GET → formulario de carga.
    POST → procesa archivos, genera previsualización y embebe los datos
            en el template (sin usar sesión ni base de datos).
    """
    if request.method == "GET":
        return render(request, "upload.html")

    # Leer archivos subidos
    reporte_file = request.FILES.get("reporte")
    trabajadores_file = request.FILES.get("trabajadores")
    infra_file = request.FILES.get("infra")

    errors = []
    if not reporte_file:
        errors.append("Falta el archivo Reporte de empleados.")
    if not trabajadores_file:
        errors.append("Falta el archivo Trabajadores Vigentes.")
    if not infra_file:
        errors.append("Falta el archivo INFRA base.")

    if errors:
        return render(request, "upload.html", {"errors": errors})

    # Parsear
    try:
        df_rep = parse_reporte(reporte_file)
    except Exception as e:
        return render(request, "upload.html",
                      {"errors": [f"Error leyendo Reporte: {e}"]})

    try:
        df_trab = parse_trabajadores(trabajadores_file)
    except Exception as e:
        return render(request, "upload.html",
                      {"errors": [f"Error leyendo Trabajadores: {e}"]})

    # Leer INFRA como bytes y codificar a base64 para enviar al cliente
    infra_bytes = infra_file.read()
    infra_base64 = base64.b64encode(infra_bytes).decode('ascii')

    # Convertir DataFrames a listas de diccionarios (JSON serializable)
    reporte_data = df_rep.to_dict(orient='records')
    trabajadores_data = df_trab.to_dict(orient='records')

    # Previsualizaciones
    cruce_preview = build_cruce_preview(df_trab)
    emp_preview = build_emp_preview(df_rep)

    context = {
        "cruce_preview": cruce_preview[:20],
        "emp_preview": emp_preview[:20],
        "total_trabajadores": len(df_trab),
        "total_empleados": len(df_rep),
        "cruce_cols": list(cruce_preview[0].keys()) if cruce_preview else [],
        "emp_cols": list(emp_preview[0].keys()) if emp_preview else [],
        # Datos completos embebidos en el template
        "reporte_data_json": json.dumps(reporte_data, default=str),
        "trabajadores_data_json": json.dumps(trabajadores_data, default=str),
        "infra_base64": infra_base64,
    }
    return render(request, "dashboard.html", context)


@require_POST
@csrf_exempt   # Solo por simplicidad; en producción usar CSRF con token adecuado
def download_infra(request):
    """
    Recibe los datos desde el cliente (reporte, trabajadores e infra base64),
    reconstruye los DataFrames y el archivo INFRA original, y devuelve el Excel final.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    reporte_data = data.get("reporte_data")
    trabajadores_data = data.get("trabajadores_data")
    infra_base64 = data.get("infra_base64")

    if not all([reporte_data, trabajadores_data, infra_base64]):
        return JsonResponse({"error": "Faltan datos necesarios"}, status=400)

    try:
        # Reconstruir DataFrames
        df_rep = pd.DataFrame(reporte_data)
        df_trab = pd.DataFrame(trabajadores_data)
        # Decodificar INFRA
        infra_bytes = base64.b64decode(infra_base64)
    except Exception as e:
        return JsonResponse({"error": f"Error al reconstruir datos: {e}"}, status=400)

    try:
        output_bytes = generate_infra(infra_bytes, df_rep, df_trab)
    except Exception as e:
        return JsonResponse({"error": f"Error generando archivo: {e}"}, status=500)

    response = HttpResponse(
        output_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="INFRA_Cruce_ARL_actualizado.xlsx"'
    return response