import tkinter as tk
from tkinter import messagebox, font as tkfont
import threading
import queue
import time
import json
import os
from datetime import datetime
from typing import List, Tuple, Dict
import sys

# ═══════════════════════════════════════════════════════════════
#  GESTOR DE VOZ - VERSIÓN MEJORADA Y ROBUSTA
# ═══════════════════════════════════════════════════════════════

class GestorVozAvanzado:
    """
    Gestor robusto de síntesis de voz con soporte para múltiples backends.
    Si pyttsx3 falla, intenta con espeak o festival.
    """
    def __init__(self):
        self.tipo_engine = None
        self.engine = None
        self.cola = queue.Queue()
        self.ocupada = threading.Event()
        self.hablando = False
        
        self._inicializar_engine()
        self._iniciar_worker()
    
    def _inicializar_engine(self):
        """Intenta inicializar pyttsx3, si falla usa alternativas"""
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 130)  # Velocidad más lenta para claridad
            self.engine.setProperty('volume', 1.0)
            
            # Intentar configurar voz en español
            voices = self.engine.getProperty('voices')
            for v in voices:
                if 'es' in str(v.id).lower() or 'spanish' in str(v.name).lower():
                    self.engine.setProperty('voice', v.id)
                    break
            
            self.tipo_engine = 'pyttsx3'
            print("✅ pyttsx3 inicializado correctamente")
            return True
        except ImportError:
            print("⚠️  pyttsx3 no disponible, intentando con alternativas...")
            return self._intentar_alternativas()
    
    def _intentar_alternativas(self):
        """Intenta usar espeak u otros motores del sistema"""
        import subprocess
        
        # Probar espeak
        try:
            result = subprocess.run(['which', 'espeak'], capture_output=True)
            if result.returncode == 0:
                self.tipo_engine = 'espeak'
                print("✅ espeak detectado y disponible")
                return True
        except:
            pass
        
        # Probar festival
        try:
            result = subprocess.run(['which', 'festival'], capture_output=True)
            if result.returncode == 0:
                self.tipo_engine = 'festival'
                print("✅ festival detectado y disponible")
                return True
        except:
            pass
        
        # Fallback: solo texto sin audio
        self.tipo_engine = 'texto_solamente'
        print("⚠️  Sin síntesis de voz disponible. Solo se mostrarán preguntas por texto.")
        return False
    
    def _iniciar_worker(self):
        """Inicia el thread worker que procesa el audio"""
        def worker():
            while True:
                item = self.cola.get()
                if item is None:
                    break
                
                texto = item
                self.hablando = True
                self.ocupada.set()
                
                try:
                    self._hablar_ahora(texto)
                except Exception as e:
                    print(f"Error al hablar: {e}")
                finally:
                    self.hablando = False
                    self.ocupada.clear()
                    self.cola.task_done()
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    def _hablar_ahora(self, texto: str):
        """Realiza la síntesis de voz según el engine disponible"""
        import subprocess
        
        if self.tipo_engine == 'pyttsx3':
            try:
                self.engine.say(texto)
                self.engine.runAndWait()
            except Exception as e:
                print(f"Error pyttsx3: {e}")
        
        elif self.tipo_engine == 'espeak':
            try:
                subprocess.run(
                    ['espeak', '-v', 'es', '-s', '130', texto],
                    timeout=10
                )
            except Exception as e:
                print(f"Error espeak: {e}")
        
        elif self.tipo_engine == 'festival':
            try:
                subprocess.run(
                    ['echo', texto, '|', 'festival', '--tts'],
                    timeout=10,
                    shell=True
                )
            except Exception as e:
                print(f"Error festival: {e}")
        
        elif self.tipo_engine == 'texto_solamente':
            # Solo simular que está hablando
            print(f"[LECTOR]: {texto}")
            time.sleep(len(texto) * 0.05)  # Simular tiempo de lectura
    
    def hablar(self, texto: str):
        """Cola el texto para ser leído en voz alta"""
        # Limpiar cola anterior
        while not self.cola.empty():
            try:
                self.cola.get_nowait()
                self.cola.task_done()
            except queue.Empty:
                break
        
        # Agregar nuevo texto
        self.cola.put(texto)
    
    def detener(self):
        """Detiene la síntesis de voz actual"""
        while not self.cola.empty():
            try:
                self.cola.get_nowait()
                self.cola.task_done()
            except queue.Empty:
                break
        
        if self.tipo_engine == 'pyttsx3' and self.engine:
            try:
                self.engine.stop()
            except:
                pass
    
    def esta_hablando(self) -> bool:
        """Verifica si está hablando en este momento"""
        return self.hablando
    
    def esperar_finalizacion(self, timeout: float = 5):
        """Espera a que finalice la síntesis de voz"""
        tiempo_inicio = time.time()
        while self.hablando:
            if time.time() - tiempo_inicio > timeout:
                break
            time.sleep(0.1)

# ═══════════════════════════════════════════════════════════════
#  FILTRO DE CONTENIDO
# ═══════════════════════════════════════════════════════════════
PALABRAS_PROHIBIDAS = [
    "mierda"
]

def validar_contenido(texto: str) -> bool:
    """Verifica si el texto contiene lenguaje inapropiado"""
    texto_limpio = texto.lower()
    return not any(p in texto_limpio for p in PALABRAS_PROHIBIDAS)

# ═══════════════════════════════════════════════════════════════
#  BASE DE DATOS DE FLASHCARDS - CONTENIDO MEJORADO
# ═══════════════════════════════════════════════════════════════
CATEGORIAS_FLASHCARDS = {
    "Geografía": [
        ("¿Capital de Francia?", "paris"),
        ("¿Capital de México?", "ciudad de mexico"),
        ("¿Capital de Japón?", "tokio"),
        ("¿En qué continente está Brasil?", "america"),
        ("¿Cuál es el país más grande del mundo?", "rusia"),
        ("¿Capital de Alemania?", "berlin"),
        ("¿Capital de España?", "madrid"),
        ("¿Capital de Italia?", "roma"),
    ],
    "Matemáticas": [
        ("¿Cuánto es dos más dos?", "4"),
        ("¿Cuántos lados tiene un triángulo?", "3"),
        ("¿Cuál es el resultado de cinco por seis?", "30"),
        ("¿Cuánto es cien dividido entre cuatro?", "25"),
        ("¿Cuál es el doble de quince?", "30"),
        ("¿Cuánto es siete al cuadrado?", "49"),
        ("¿Cuál es la raíz cuadrada de ciento cuarenta y cuatro?", "12"),
        ("¿Cuánto es tres por tres por tres?", "27"),
    ],
    "Ciencia": [
        ("¿De qué color es el cielo?", "azul"),
        ("¿Cuál es el planeta más grande del sistema solar?", "jupiter"),
        ("¿Cuántos huesos tiene el cuerpo humano adulto?", "206"),
        ("¿Cuál es el gas más abundante en la atmósfera?", "nitrogeno"),
        ("¿A qué temperatura hierve el agua?", "cien grados"),
        ("¿Cuál es el elemento más ligero?", "hidrogeno"),
        ("¿Cuántos continentes hay?", "7"),
        ("¿Cuál es la velocidad aproximada de la luz?", "trescientos mil kilometros"),
    ],
    "Historia": [
        ("¿En qué año se descubrió América?", "mil cuatrocientos noventa y dos"),
        ("¿Quién fue el primer presidente de México?", "guadalupe victoria"),
        ("¿En qué siglo ocurrió la Revolución Francesa?", "dieciocho"),
        ("¿Quién pintó la Mona Lisa?", "leonardo da vinci"),
        ("¿En qué año terminó la Segunda Guerra Mundial?", "mil novecientos cuarenta y cinco"),
        ("¿Cuál fue la antigua capital del Perú prehispánico?", "cuzco"),
        ("¿Quién escribió el Quijote?", "miguel de cervantes"),
        ("¿En qué año cayó el Muro de Berlín?", "mil novecientos ochenta y nueve"),
    ],
    "Literatura": [
        ("¿Quién escribió Cien años de soledad?", "gabriel garcia marquez"),
        ("¿Quién es el autor de Don Quijote?", "miguel de cervantes"),
        ("¿Quién escribió El príncipe feliz?", "oscar wilde"),
        ("¿Cuál es el libro más vendido de todos los tiempos?", "la biblia"),
        ("¿Quién escribió Orgullo y prejuicio?", "jane austen"),
        ("¿Quién es autor de mil novecientos ochenta y cuatro?", "george orwell"),
        ("¿Quién escribió El retrato de Dorian Gray?", "oscar wilde"),
        ("¿Cuál es la novela más famosa de Julio Verne?", "viaje al centro de la tierra"),
    ],
}

# ═══════════════════════════════════════════════════════════════
#  GESTOR DE ESTADÍSTICAS
# ═══════════════════════════════════════════════════════════════
class EstadisticasManager:
    """Gestiona y almacena las estadísticas del usuario"""
    def __init__(self, archivo: str = "estadisticas.json"):
        self.archivo = archivo
        self.datos = self._cargar()
    
    def _cargar(self) -> Dict:
        if os.path.exists(self.archivo):
            try:
                with open(self.archivo, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"sesiones": [], "puntos_totales": 0}
        return {"sesiones": [], "puntos_totales": 0}
    
    def _guardar(self):
        with open(self.archivo, 'w', encoding='utf-8') as f:
            json.dump(self.datos, f, ensure_ascii=False, indent=2)
    
    def agregar_sesion(self, categoria: str, puntos: int, total: int):
        """Registra una nueva sesión completada"""
        sesion = {
            "fecha": datetime.now().isoformat(),
            "categoria": categoria,
            "puntos": puntos,
            "total": total,
            "porcentaje": int((puntos / total) * 100) if total > 0 else 0
        }
        self.datos["sesiones"].append(sesion)
        self.datos["puntos_totales"] += puntos
        self._guardar()
    
    def obtener_resumen(self) -> Dict:
        """Retorna resumen de estadísticas"""
        if not self.datos["sesiones"]:
            return {
                "sesiones_totales": 0,
                "promedio": 0,
                "mejor_puntuacion": 0,
                "puntos_totales": 0
            }
        
        sesiones = self.datos["sesiones"]
        porcentajes = [s["porcentaje"] for s in sesiones]
        
        return {
            "sesiones_totales": len(sesiones),
            "promedio": sum(porcentajes) // len(porcentajes),
            "mejor_puntuacion": max(porcentajes),
            "puntos_totales": self.datos["puntos_totales"]
        }

# ═══════════════════════════════════════════════════════════════
#  PALETA DE COLORES Y CONSTANTES DE DISEÑO
# ═══════════════════════════════════════════════════════════════
BG_PRINCIPAL   = "#0F0E17"
BG_CARD        = "#1A1927"
BG_CARD_ALT    = "#232130"
ACCENT_MORADO  = "#9D4EDD"
ACCENT_ROSA    = "#FF006E"
ACCENT_CIAN    = "#00D9FF"
ACCENT_VERDE   = "#3A86FF"
TEXT_PRIMARY   = "#F5F5F5"
TEXT_SECONDARY = "#A0A0B0"
SUCCESS_GREEN  = "#06FFA5"
ERROR_RED      = "#FF6B6B"
WARNING_GOLD   = "#FFD60A"

# ═══════════════════════════════════════════════════════════════
#  COMPONENTES UI PERSONALIZADOS
# ═══════════════════════════════════════════════════════════════
class BotonesModernos:
    """Factory de botones con estilos modernos"""
    
    @staticmethod
    def primario(parent, text: str, command, ancho=16):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=ACCENT_MORADO, fg=TEXT_PRIMARY,
            activebackground=ACCENT_ROSA, activeforeground=TEXT_PRIMARY,
            font=("Courier New", 11, "bold"),
            width=ancho, relief="flat", cursor="hand2",
            bd=0, padx=10, pady=8,
            highlightthickness=0,
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT_ROSA))
        btn.bind("<Leave>", lambda e: btn.config(bg=ACCENT_MORADO))
        return btn
    
    @staticmethod
    def secundario(parent, text: str, command, ancho=16):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=BG_CARD_ALT, fg=ACCENT_CIAN,
            activebackground=BG_CARD, activeforeground=ACCENT_CIAN,
            font=("Courier New", 10),
            width=ancho, relief="solid", cursor="hand2",
            bd=2, padx=10, pady=6,
            highlightthickness=0,
        )
        return btn
    
    @staticmethod
    def exito(parent, text: str, command, ancho=16):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=SUCCESS_GREEN, fg="#000000",
            activebackground=ACCENT_CIAN, activeforeground="#000000",
            font=("Courier New", 11, "bold"),
            width=ancho, relief="flat", cursor="hand2",
            bd=0, padx=10, pady=8,
            highlightthickness=0,
        )
        return btn

class BarraProgresoModerna(tk.Canvas):
    """Barra de progreso con animación suave"""
    def __init__(self, parent, ancho=450, alto=6, **kw):
        super().__init__(
            parent, width=ancho, height=alto,
            bg=BG_CARD_ALT, highlightthickness=0, **kw
        )
        self.ancho = ancho
        self.alto = alto
        self.fondo = self.create_rectangle(0, 0, ancho, alto, fill=BG_CARD, outline="")
        self.barra = self.create_rectangle(0, 0, 0, alto, fill=ACCENT_MORADO, outline="")
    
    def establecer(self, fraccion: float):
        """Establece el progreso (0.0 a 1.0)"""
        ancho_relleno = max(0, int(self.ancho * fraccion))
        self.coords(self.barra, 0, 0, ancho_relleno, self.alto)

# ═══════════════════════════════════════════════════════════════
#  LÓGICA PRINCIPAL DEL JUEGO
# ═══════════════════════════════════════════════════════════════
class AplicacionEstudio:
    def __init__(self, ventana_principal):
        self.root = ventana_principal
        self.voz = GestorVozAvanzado()
        self.estadisticas = EstadisticasManager()
        
        # Estado del juego
        self.flashcards = []
        self.categoria_actual = None
        self.indice = 0
        self.puntos = 0
        self.activo = False
        
        self._construir_ui()
    
    def _construir_ui(self):
        """Construye la interfaz de usuario"""
        self.root.title("📚 Estudio Inteligente con Voz")
        self.root.geometry("620x750")
        self.root.configure(bg=BG_PRINCIPAL)
        self.root.resizable(False, False)
        
        # Encabezado
        self._crear_encabezado()
        
        # Separador
        tk.Frame(self.root, height=1, bg=ACCENT_MORADO).pack(fill="x", padx=0, pady=10)
        
        # Marco de selección
        self.frame_seleccion = tk.Frame(self.root, bg=BG_PRINCIPAL)
        self.frame_seleccion.pack(fill="both", expand=True, padx=20, pady=10)
        self._crear_pantalla_seleccion()
        
        # Marco de juego
        self.frame_juego = tk.Frame(self.root, bg=BG_PRINCIPAL)
        self._crear_pantalla_juego()
    
    def _crear_encabezado(self):
        """Crea el encabezado de la aplicación"""
        frame_header = tk.Frame(self.root, bg=BG_PRINCIPAL)
        frame_header.pack(fill="x", padx=20, pady=(15, 5))
        
        tk.Label(
            frame_header,
            text="📚  ESTUDIO INTELIGENTE",
            font=("Courier New", 20, "bold"),
            bg=BG_PRINCIPAL,
            fg=ACCENT_MORADO
        ).pack(anchor="w")
        
        tk.Label(
            frame_header,
            text="Aprende con voz, responde y mejora tu puntaje",
            font=("Courier New", 10),
            bg=BG_PRINCIPAL,
            fg=TEXT_SECONDARY
        ).pack(anchor="w", pady=(2, 0))
    
    def _crear_pantalla_seleccion(self):
        """Crea la pantalla de selección de categorías"""
        tk.Label(
            self.frame_seleccion,
            text="Elige una categoría para comenzar:",
            font=("Courier New", 12, "bold"),
            bg=BG_PRINCIPAL,
            fg=TEXT_PRIMARY
        ).pack(pady=(10, 20), anchor="w")
        
        frame_categorias = tk.Frame(self.frame_seleccion, bg=BG_PRINCIPAL)
        frame_categorias.pack(fill="both", expand=True)
        
        for i, categoria in enumerate(CATEGORIAS_FLASHCARDS.keys()):
            fila = i // 2
            columna = i % 2
            
            btn = tk.Button(
                frame_categorias,
                text=f"📖  {categoria}",
                command=lambda c=categoria: self.iniciar_con_categoria(c),
                bg=BG_CARD_ALT,
                fg=ACCENT_CIAN,
                activebackground=ACCENT_MORADO,
                activeforeground=TEXT_PRIMARY,
                font=("Courier New", 12, "bold"),
                relief="solid",
                bd=2,
                padx=20,
                pady=15,
                cursor="hand2",
                highlightthickness=0,
            )
            btn.grid(row=fila, column=columna, padx=10, pady=10, sticky="nsew")
        
        for i in range(3):
            frame_categorias.grid_rowconfigure(i, weight=1)
        for i in range(2):
            frame_categorias.grid_columnconfigure(i, weight=1)
        
        # Estadísticas
        tk.Frame(self.frame_seleccion, height=1, bg=TEXT_SECONDARY).pack(fill="x", pady=15)
        self._crear_panel_estadisticas()
    
    def _crear_panel_estadisticas(self):
        """Crea panel con estadísticas del usuario"""
        stats = self.estadisticas.obtener_resumen()
        
        frame_stats = tk.Frame(self.frame_seleccion, bg=BG_CARD)
        frame_stats.pack(fill="x")
        
        tk.Label(
            frame_stats,
            text="📊  Tus Estadísticas",
            font=("Courier New", 11, "bold"),
            bg=BG_CARD,
            fg=ACCENT_VERDE
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        info_text = (
            f"Sesiones: {stats['sesiones_totales']} | "
            f"Promedio: {stats['promedio']}% | "
            f"Mejor: {stats['mejor_puntuacion']}% | "
            f"Puntos: {stats['puntos_totales']}"
        )
        
        tk.Label(
            frame_stats,
            text=info_text,
            font=("Courier New", 9),
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            wraplength=550
        ).pack(anchor="w", padx=15, pady=(0, 10))
    
    def _crear_pantalla_juego(self):
        """Crea la pantalla de juego"""
        # Barra de progreso
        frame_progreso = tk.Frame(self.frame_juego, bg=BG_PRINCIPAL)
        frame_progreso.pack(fill="x", pady=(5, 10))
        
        self.lbl_progreso = tk.Label(
            frame_progreso,
            text="",
            font=("Courier New", 10),
            bg=BG_PRINCIPAL,
            fg=TEXT_SECONDARY
        )
        self.lbl_progreso.pack(side="left", anchor="w")
        
        self.lbl_puntos = tk.Label(
            frame_progreso,
            text="⭐  0 pts",
            font=("Courier New", 10, "bold"),
            bg=BG_PRINCIPAL,
            fg=ACCENT_ROSA
        )
        self.lbl_puntos.pack(side="right", anchor="e")
        
        self.barra_progreso = BarraProgresoModerna(self.frame_juego, ancho=580)
        self.barra_progreso.pack(pady=(0, 15))
        
        # Tarjeta de pregunta
        frame_pregunta = tk.Frame(self.frame_juego, bg=BG_CARD)
        frame_pregunta.pack(fill="x", pady=5, padx=0, ipady=25)
        
        tk.Frame(frame_pregunta, height=3, bg=ACCENT_MORADO).pack(fill="x")
        
        self.lbl_pregunta = tk.Label(
            frame_pregunta,
            text="",
            wraplength=500,
            font=("Courier New", 14, "bold"),
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            justify="center"
        )
        self.lbl_pregunta.pack(padx=20, pady=20)
        
        # Campo de respuesta
        self.entry_respuesta = tk.Entry(
            self.frame_juego,
            font=("Courier New", 12),
            width=35,
            justify="center",
            bg=BG_CARD_ALT,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT_CIAN,
            relief="flat",
            bd=6,
            highlightthickness=0,
        )
        self.entry_respuesta.pack(pady=10)
        self.entry_respuesta.bind("<Return>", lambda e: self.verificar_respuesta())
        
        # Mensaje de resultado
        self.lbl_resultado = tk.Label(
            self.frame_juego,
            text="",
            font=("Courier New", 11, "bold"),
            bg=BG_PRINCIPAL,
            fg=TEXT_PRIMARY
        )
        self.lbl_resultado.pack(pady=5)
        
        # Botones de acción
        frame_botones = tk.Frame(self.frame_juego, bg=BG_PRINCIPAL)
        frame_botones.pack(pady=12)
        
        self.btn_responder = BotonesModernos.exito(
            frame_botones, "✔  Responder", self.verificar_respuesta, ancho=12
        )
        self.btn_responder.pack(side="left", padx=5)
        
        self.btn_repetir = BotonesModernos.secundario(
            frame_botones, "🔊  Repetir", self.repetir_pregunta, ancho=12
        )
        self.btn_repetir.pack(side="left", padx=5)
        
        self.btn_salir = BotonesModernos.secundario(
            frame_botones, "❌  Salir", self.salir_a_inicio, ancho=12
        )
        self.btn_salir.pack(side="left", padx=5)
        
        # Botón de reinicio
        self.btn_reinicio = BotonesModernos.primario(
            self.frame_juego, "🔄  Jugar de nuevo", self.reiniciar, ancho=14
        )
    
    def iniciar_con_categoria(self, categoria: str):
        """Inicia el juego con una categoría seleccionada"""
        self.categoria_actual = categoria
        self.flashcards = list(CATEGORIAS_FLASHCARDS[categoria])
        self.indice = 0
        self.puntos = 0
        self.activo = True
        
        # Cambiar pantalla
        self.frame_seleccion.pack_forget()
        self.frame_juego.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Iniciar juego
        print(f"\n🎮 Iniciando: {categoria}")
        print(f"Total de preguntas: {len(self.flashcards)}\n")
        
        # Mensaje de inicio con voz
        mensaje_inicio = f"Iniciando test de {categoria}. Tienes {len(self.flashcards)} preguntas. Buena suerte."
        self.voz.hablar(mensaje_inicio)
        
        # Mostrar primera pregunta después de que termine el mensaje inicial
        self.root.after(2000, self.mostrar_pregunta)
    
    def mostrar_pregunta(self):
        """Muestra la pregunta actual"""
        if not self.activo or self.indice >= len(self.flashcards):
            self.finalizar()
            return
        
        pregunta, respuesta_correcta = self.flashcards[self.indice]
        
        # Actualizar UI
        self.lbl_pregunta.config(text=pregunta)
        self.lbl_progreso.config(
            text=f"Pregunta {self.indice + 1} de {len(self.flashcards)}"
        )
        self.barra_progreso.establecer(self.indice / len(self.flashcards))
        self.lbl_resultado.config(text="")
        self.entry_respuesta.config(state="normal")
        self.entry_respuesta.delete(0, tk.END)
        self.entry_respuesta.focus_set()
        
        # Leer pregunta en voz alta - TEXTO CLARO Y DIRECTO
        numero_pregunta = self.indice + 1
        texto_voz = f"Pregunta número {numero_pregunta}. {pregunta}"
        
        print(f"\n📝 Pregunta {numero_pregunta}:")
        print(f"   {pregunta}")
        print(f"   Respuesta esperada: {respuesta_correcta}")
        print(f"🔊 Leyendo: {texto_voz}\n")
        
        # Ejecutar síntesis de voz
        self.voz.hablar(texto_voz)
    
    def repetir_pregunta(self):
        """Repite la pregunta actual"""
        if self.activo and self.indice < len(self.flashcards):
            pregunta, _ = self.flashcards[self.indice]
            numero_pregunta = self.indice + 1
            texto_voz = f"Pregunta número {numero_pregunta}. {pregunta}"
            
            print(f"Repitiendo pregunta {numero_pregunta}")
            self.voz.detener()
            self.voz.hablar(texto_voz)
    
    def verificar_respuesta(self):
        """Verifica si la respuesta es correcta"""
        if not self.activo or self.indice >= len(self.flashcards):
            return
        
        usuario = self.entry_respuesta.get().lower().strip()
        _, respuesta_correcta = self.flashcards[self.indice]
        
        if not usuario:
            self.lbl_resultado.config(
                text="✏  Por favor escribe una respuesta",
                fg=WARNING_GOLD
            )
            self.voz.hablar("Por favor escribe una respuesta")
            return
        
        # Normalizar y comparar respuestas
        usuario_normalizado = self._normalizar_respuesta(usuario)
        respuesta_normalizada = self._normalizar_respuesta(respuesta_correcta)
        
        es_correcto = usuario_normalizado == respuesta_normalizada
        
        print(f"Respuesta del usuario: '{usuario}'")
        print(f"Respuesta correcta: '{respuesta_correcta}'")
        print(f"¿Correcto?: {es_correcto}\n")
        
        if es_correcto:
            self.puntos += 1
            self.lbl_resultado.config(
                text="✔  ¡Correcto!",
                fg=SUCCESS_GREEN
            )
            self.voz.hablar("Correcto. Excelente.")
        else:
            self.lbl_resultado.config(
                text=f"✘  Respuesta correcta: {respuesta_correcta}",
                fg=ERROR_RED
            )
            texto_error = f"Incorrecto. La respuesta correcta es {respuesta_correcta}."
            self.voz.hablar(texto_error)
        
        self.lbl_puntos.config(text=f"⭐  {self.puntos} pts")
        self.entry_respuesta.config(state="disabled")
        self.indice += 1
        
        # Pausa antes de siguiente pregunta
        self.root.after(2000, self.mostrar_pregunta)
    
    def finalizar(self):
        """Finaliza el juego y muestra resultados"""
        self.activo = False
        
        total = len(self.flashcards)
        porcentaje = int((self.puntos / total) * 100) if total > 0 else 0
        
        # Guardar estadísticas
        self.estadisticas.agregar_sesion(self.categoria_actual, self.puntos, total)
        
        self.lbl_pregunta.config(
            text=f"🏆  ¡Test completado!",
            fg=ACCENT_VERDE
        )
        self.lbl_resultado.config(
            text=f"Obtuviste {self.puntos} de {total} ({porcentaje}%)",
            fg=ACCENT_ROSA
        )
        self.barra_progreso.establecer(1.0)
        self.entry_respuesta.config(state="disabled")
        self.btn_responder.config(state="disabled")
        self.btn_repetir.config(state="disabled")
        
        self.btn_reinicio.pack(pady=10)
        
        print(f"\n" + "="*50)
        print(f"✅ TEST COMPLETADO")
        print(f"   Categoría: {self.categoria_actual}")
        print(f"   Puntuación: {self.puntos} de {total} ({porcentaje}%)")
        print(f"="*50 + "\n")
        
        # Mensaje de felicitación
        mensaje = f"Excelente. Completaste el test con {porcentaje} por ciento de aciertos."
        self.voz.hablar(mensaje)
    
    def salir_a_inicio(self):
        """Regresa a la pantalla de inicio"""
        self.activo = False
        self.voz.detener()
        self.frame_juego.pack_forget()
        self.btn_reinicio.pack_forget()
        
        # Recrear pantalla de selección
        self.frame_seleccion.destroy()
        self.frame_seleccion = tk.Frame(self.root, bg=BG_PRINCIPAL)
        self.frame_seleccion.pack(fill="both", expand=True, padx=20, pady=10)
        self._crear_pantalla_seleccion()
    
    def reiniciar(self):
        """Reinicia el juego con la misma categoría"""
        self.indice = 0
        self.puntos = 0
        self.activo = True
        
        self.btn_reinicio.pack_forget()
        self.btn_responder.config(state="normal")
        self.btn_repetir.config(state="normal")
        self.lbl_resultado.config(text="")
        
        print(f"\n🔄 Reiniciando {self.categoria_actual}...\n")
        self.root.after(500, self.mostrar_pregunta)
    
    @staticmethod
    def _normalizar_respuesta(texto: str) -> str:
        """Normaliza respuestas para comparación flexible"""
        texto = " ".join(texto.split())
        acentos = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
        }
        for acentuada, normal in acentos.items():
            texto = texto.replace(acentuada, normal)
        return texto

# ═══════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "="*60)
    print("📚 APLICACIÓN DE ESTUDIO CON VOZ - INICIANDO")
    print("="*60)
    print("\nVerificando disponibilidad de síntesis de voz...")
    
    root = tk.Tk()
    app = AplicacionEstudio(root)
    
    print("\n✅ Interfaz gráfica lista")
    print("   Elige una categoría y comienza a aprender!\n")
    
    root.mainloop()
    print("\n👋 Aplicación cerrada.")
