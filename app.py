from flask import Flask, render_template

app = Flask(__name__)

ANIMALS = [
    {
        "id": "medusa",
        "name": "Medusa",
        "img": "/static/img/medusa.png",
        "info": {
            "cientifico": "Aurelia aurita",
            "caracteres": {
                "texto": "Sin cerebro ni corazón...",
                "img": "/static/img/medusa-caracteristicas.png"
            }
        }
    }
]

@app.route("/")
def index():
    return render_template(
        "index.html",
        animals=ANIMALS
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

