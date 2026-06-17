# Image Quality Reviewer

Una aplicación de escritorio local para revisar carpetas de imágenes y detectar archivos posiblemente rotos o inusables.

El proyecto está pensado especialmente para trabajar con carpetas grandes de imágenes, como datasets de personas, donde puede haber archivos corruptos, incompletos o visualmente dañados.

La app permite escanear una carpeta, revisar los casos detectados, previsualizar cada imagen y mover archivos sospechosos a una carpeta local `trash/` con confirmación.

---

## Objetivo

El objetivo principal no es evaluar si una foto es “linda”, “nítida” o “perfecta”.

El objetivo es ayudar a encontrar imágenes que probablemente no sirvan porque están realmente dañadas, por ejemplo:

* archivos que no se pueden abrir;
* imágenes incompletas o truncadas;
* archivos con estructura inválida;
* imágenes con ruido RGB extremo;
* posibles casos de corrupción visual fuerte.

---

## Qué NO intenta hacer

La herramienta intenta evitar falsos positivos en imágenes válidas.

Por eso, en el modo actual, no debería marcar una imagen como inusable solo por:

* baja resolución;
* fondo desenfocado;
* blur leve o moderado;
* carteles en el fondo;
* telas, paredes, sombras o luces;
* objetos detrás de una persona;
* compresión o calidad visual baja.

Estos casos pueden ser imperfectos, pero no necesariamente hacen que una imagen sea inválida.

---

## Estado actual del proyecto

El proyecto está en una etapa experimental.

Ya cuenta con:

* interfaz gráfica local con Tkinter;
* análisis de imágenes con Pillow;
* detección visual experimental con OpenCV y NumPy;
* escaneo de carpetas y subcarpetas;
* previsualización de imágenes detectadas;
* marcado manual de archivos;
* movimiento seguro a carpeta `trash/`;
* generación de reportes en Markdown;
* análisis en segundo plano para evitar que la ventana se congele.

Todavía se está ajustando la detección visual para reducir falsos positivos sin dejar pasar imágenes claramente rotas.

---

## Tecnologías usadas

* Python
* Tkinter
* Pillow
* OpenCV
* NumPy

---

## Estructura del proyecto

```text
image-quality-reviewer/
│
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── reports/
├── trash/
│
└── src/
    ├── __init__.py
    ├── scanner.py
    ├── image_analysis.py
    ├── corruption_detection.py
    ├── image_preview.py
    ├── file_actions.py
    ├── report.py
    ├── settings.py
    └── ui.py
```

---

## Instalación

Crear y activar un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación del entorno:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

Instalar dependencias:

```powershell
pip install -r requirements.txt
```

---

## Dependencias

El archivo `requirements.txt` actual usa:

```txt
Pillow==10.4.0
numpy>=1.26,<3
opencv-python>=4.10,<5
```

---

## Uso

Ejecutar la aplicación:

```powershell
python main.py
```

Luego:

1. Seleccionar una carpeta de imágenes.
2. Ejecutar el escaneo.
3. Revisar los archivos detectados.
4. Previsualizar cada imagen.
5. Marcar o desmarcar imágenes manualmente.
6. Mover archivos seleccionados o marcados a `trash/`.
7. Generar un reporte si hace falta.

---

## Cómo clasifica los resultados

La herramienta separa los resultados en distintos niveles internos:

### Unusable

Imágenes que probablemente están rotas o no son utilizables.

Ejemplos:

* archivo que no abre;
* archivo vacío;
* imagen incompleta;
* estructura inválida;
* error de lectura;
* corrupción visual extrema.

### Review

Casos visualmente sospechosos, pero no lo suficientemente seguros como para descartarlos automáticamente.

Ejemplos:

* posible panel dañado;
* posible corte visual;
* posible patrón de ruido;
* señales ambiguas que podrían venir del fondo.

Por defecto, estos casos no se muestran si `SHOW_WARNINGS_IN_UI` está en `False`.

### Info

Información útil, pero no bloqueante.

Ejemplos:

* baja resolución;
* posible blur;
* tamaño de archivo sospechosamente bajo.

---

## Configuración importante

En `src/settings.py` se puede controlar el comportamiento de la app.

Para mostrar solo imágenes clasificadas como inusables:

```python
SHOW_WARNINGS_IN_UI = False
```

Para mostrar también casos que requieren revisión manual:

```python
SHOW_WARNINGS_IN_UI = True
```

Para datasets de personas, se recomienda mantenerlo en:

```python
SHOW_WARNINGS_IN_UI = False
```

Esto ayuda a evitar que imágenes válidas aparezcan como problemas solo por tener fondos complejos, blur o elementos detrás.

---

## Seguridad

La aplicación no borra archivos de forma permanente automáticamente.

Cuando se decide mover una imagen, el archivo se envía a la carpeta local:

```text
trash/
```

Antes de mover archivos, la app pide confirmación.

---

## Reportes

Los reportes se generan en formato Markdown dentro de:

```text
reports/
```

Incluyen información como:

* carpeta analizada;
* cantidad de archivos listados;
* dimensiones;
* blur score;
* motivos detectados;
* estado de cada imagen.

---

## Limitaciones actuales

Detectar imágenes rotas no es trivial.

Algunas imágenes visualmente dañadas pueden abrirse correctamente y no tener errores estructurales. En esos casos, el programa necesita inferir si la imagen está realmente rota o si solo tiene elementos visuales normales como fondos, luces, carteles o telas.

Por eso, el proyecto prioriza evitar falsos positivos.

Esto significa que algunas imágenes sospechosas pueden requerir revisión manual.

---

## Próximos pasos posibles

Algunas mejoras posibles:

* mejorar el sistema de scoring visual;
* separar mejor `Unusable` de `Review`;
* agregar una vista opcional para revisar casos dudosos;
* guardar métricas internas en el reporte;
* permitir configurar sensibilidad desde la interfaz;
* entrenar o usar un modelo específico con ejemplos reales de imágenes buenas y rotas;
* mejorar la interfaz visual;
* agregar empaquetado como `.exe` para Windows.

---

## Nota

Esta herramienta es un apoyo para revisión local de imágenes.

No reemplaza una revisión humana ni garantiza que todos los casos sean detectados correctamente.
