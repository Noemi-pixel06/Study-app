"""
Océano Quiz — Servidor Flask
============================
Expone tres grupos de rutas:

  GET  /                    → Sirve el quiz (templates/index.html)
  POST /api/verificar-url   → Scraping + análisis de credibilidad de una URL
  POST /api/claude          → Proxy hacia la API de Anthropic (evita exponer la key en el browser)

Cómo correr localmente:
  pip install flask requests beautifulsoup4 anthropic python-dotenv
  cp .env.example .env        # luego pega tu ANTHROPIC_API_KEY
  python app.py

Variables de entorno (.env):
  ANTHROPIC_API_KEY=sk-ant-...
  FLASK_DEBUG=true            # opcional; no usar en producción
"""

import os
import json
import logging
from flask import Flask, render_template, request, jsonify

import requests
from bs4 import BeautifulSoup

# Carga .env si existe (útil en desarrollo local)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv no instalado → usa variables de entorno del sistema

# ── Configuración ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")


# ── Utilidades ─────────────────────────────────────────────────────────────────


def _anthropic_headers() -> dict:
    """Cabeceras requeridas para llamar a la API de Anthropic desde el servidor."""
    return {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }


# ── Ruta principal ─────────────────────────────────────────────────────────────


@app.route("/")
def index():
    """Sirve el frontend del quiz."""
    return render_template("index.html")


# ── Proxy de Anthropic ─────────────────────────────────────────────────────────


@app.post("/api/claude")
def claude_proxy():
    """
    Reenvía la solicitud del frontend a la API de Anthropic.
    El frontend envía el mismo body que usaría directo contra Anthropic,
    pero sin necesidad de tener la API key expuesta en el browser.

    Body esperado (JSON):
        {
          "model": "claude-sonnet-4-20250514",
          "max_tokens": 800,
          "system": "...",
          "messages": [{"role": "user", "content": "..."}]
        }
    """
    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY no configurada.")
        return jsonify({"error": "API key no configurada en el servidor."}), 500

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Body JSON requerido."}), 400

    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers=_anthropic_headers(),
            json=body,
            timeout=30,
        )
        # Devolver la respuesta tal cual (código + cuerpo) para que el frontend
        # la maneje igual que si hubiera llamado a Anthropic directamente.
        return (resp.content, resp.status_code, {"Content-Type": "application/json"})

    except requests.Timeout:
        return jsonify({"error": "Tiempo de espera agotado al contactar la IA."}), 504
    except requests.RequestException as exc:
        log.exception("Error al contactar Anthropic: %s", exc)
        return jsonify({"error": str(exc)}), 502


# ── Verificación de URL ────────────────────────────────────────────────────────


@app.post("/api/verificar-url")
def verificar_url():
    """
    Recibe una URL, descarga el HTML, extrae el texto plano y
    lo envía a Claude para evaluar la credibilidad del contenido.

    Body esperado (JSON):
        { "url": "https://ejemplo.com/articulo" }

    Respuesta:
        {
          "url": "...",
          "titulo": "...",
          "extracto": "primeros 500 caracteres...",
          "longitud_texto": 1234,
          "analisis": {           ← resultado de Claude
            "score": 72,
            "verdict": "MAYORMENTE VERDADERO",
            "tags": ["Ciencia", "Requiere contexto"],
            "explanation": "..."
          }
        }
    """
    data = request.get_json(silent=True) or {}
    url: str = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "El campo 'url' es obligatorio."}), 400
    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "La URL debe comenzar con http:// o https://"}), 400

    # 1. Descargar el HTML ──────────────────────────────────────────────────────
    try:
        page = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "OceanoQuiz-Verifier/1.0"},
        )
        page.raise_for_status()
    except requests.Timeout:
        return jsonify({"error": "La URL tardó demasiado en responder."}), 504
    except requests.RequestException as exc:
        return jsonify({"error": f"No se pudo acceder a la URL: {exc}"}), 400

    # 2. Parsear con BeautifulSoup ──────────────────────────────────────────────
    soup = BeautifulSoup(page.text, "html.parser")

    titulo = (
        soup.title.string.strip() if soup.title and soup.title.string else "Sin título"
    )

    # Eliminar scripts, estilos y nav para limpiar el texto
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    texto = soup.get_text(separator=" ", strip=True)
    # Truncar a 3 000 caracteres para no sobrepasar el context de la IA
    texto_truncado = texto[:3000]

    # 3. Enviar a Claude para análisis ─────────────────────────────────────────
    analisis = None
    if ANTHROPIC_API_KEY and texto_truncado:
        prompt_body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 600,
            "system": (
                "Eres un verificador de contenido web experto y objetivo. "
                "El usuario te enviará el texto extraído de una página web. "
                "Debes analizarlo y responder EXCLUSIVAMENTE con un objeto JSON válido, "
                "sin texto adicional ni bloques de código markdown. Formato exacto:\n"
                '{"score":75,"verdict":"MAYORMENTE VERDADERO",'
                '"tags":["Ciencia","Necesita contexto"],'
                '"explanation":"Explicación en 2-3 oraciones en español."}\n'
                "Valores posibles para verdict: VERDADERO, MAYORMENTE VERDADERO, "
                "PARCIALMENTE VERDADERO, MAYORMENTE FALSO, FALSO, SIN VERIFICAR. "
                "Score: entero de 0 a 100."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Analiza la credibilidad de este contenido web:\n\n"
                        f"Título: {titulo}\n\n"
                        f"Texto:\n{texto_truncado}"
                    ),
                }
            ],
        }
        try:
            ai_resp = requests.post(
                ANTHROPIC_API_URL,
                headers=_anthropic_headers(),
                json=prompt_body,
                timeout=30,
            )
            ai_data = ai_resp.json()
            raw = (
                ai_data.get("content", [{}])[0]
                .get("text", "")
                .strip()
                .lstrip("```json")
                .lstrip("```")
                .rstrip("```")
                .strip()
            )
            analisis = json.loads(raw)
        except Exception as exc:
            log.warning("No se pudo obtener análisis de Claude: %s", exc)
            analisis = {
                "score": 0,
                "verdict": "SIN VERIFICAR",
                "tags": ["Error de análisis"],
                "explanation": "No fue posible analizar el contenido con IA en este momento.",
            }
    else:
        analisis = {
            "score": 0,
            "verdict": "SIN VERIFICAR",
            "tags": ["Sin API key"],
            "explanation": "La verificación con IA no está disponible (API key no configurada).",
        }

    return jsonify(
        {
            "url": url,
            "titulo": titulo,
            "extracto": texto[:500],
            "longitud_texto": len(texto),
            "analisis": analisis,
        }
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        log.warning(
            "⚠ ANTHROPIC_API_KEY no encontrada. "
            "La verificación con IA estará deshabilitada."
        )

    debug = os.environ.get(
        "FLASK_DEBUG",
        "false",
    ).lower() == "true"

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=debug,
    )