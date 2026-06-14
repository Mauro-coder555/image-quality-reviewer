# image-quality-reviewer

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/UI-Tkinter-FFB000?style=for-the-badge)
![Pillow](https://img.shields.io/badge/Images-Pillow-2CA02C?style=for-the-badge)
![Windows](https://img.shields.io/badge/Windows-ready-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Local](https://img.shields.io/badge/Local%20Only-No%20APIs-6A5ACD?style=for-the-badge)

Aplicación de escritorio local para revisar carpetas con imágenes y detectar posibles problemas de calidad.

El objetivo del proyecto es ayudar a limpiar, revisar y validar grandes cantidades de imágenes de forma visual y segura, especialmente cuando vienen de descargas masivas, crawlers de imágenes o procesos automáticos de creación de datasets.

---

## Índice

- [Qué hace](#qué-hace)
- [Para qué sirve](#para-qué-sirve)
- [Instalación](#instalación)
- [Uso](#uso)
- [Criterios de detección](#criterios-de-detección)
- [Seguridad](#seguridad)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Futuras mejoras](#futuras-mejoras)

---

## Qué hace

`image-quality-reviewer` permite seleccionar una carpeta local y analizar imágenes de forma recursiva para detectar posibles problemas.

Actualmente puede detectar:

- imágenes corruptas o que no se pueden abrir
- archivos incompletos o con error de lectura
- imágenes de baja resolución
- imágenes muy pequeñas
- imágenes borrosas
- posibles artefactos visuales, manchas o zonas anómalas
- formatos no soportados
- dimensiones inválidas o inesperadas

La app muestra una lista de imágenes problemáticas, permite previsualizarlas, marcarlas y moverlas a una carpeta local `trash/`.

---

## Para qué sirve

Es útil para revisar imágenes antes de usarlas en:

- datasets de machine learning
- crawlers de imágenes
- scrapers o descargas masivas
- herramientas internas de control de calidad
- limpieza de carpetas con muchas imágenes
- revisión visual rápida antes de procesar archivos

No reemplaza una revisión humana ni una herramienta profesional de gestión de assets, pero ayuda a detectar problemas comunes de forma rápida.

---

## Instalación

Crear y activar un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instalar dependencias:

```powershell
pip install -r requirements.txt
```

Ejecutar la app:

```powershell
python main.py
```

---

## Uso

1. Abrir la aplicación.
2. Seleccionar una carpeta local.
3. Ejecutar el escaneo.
4. Revisar la lista de imágenes problemáticas.
5. Previsualizar cada imagen desde la app.
6. Marcar imágenes para descartar.
7. Mover imágenes seleccionadas o marcadas a `trash/`.
8. Generar un reporte local en `reports/`.

La navegación también permite avanzar y retroceder entre imágenes desde la interfaz.

---

## Criterios de detección

Los criterios principales se configuran en `src/settings.py`:

```python
MIN_WIDTH = 800
MIN_HEIGHT = 600
BLUR_THRESHOLD = 120.0
INCLUDE_SUBFOLDERS = True
MOVE_TO_TRASH_BY_DEFAULT = True
```

También existen criterios simples para detectar posibles artefactos visuales, como zonas demasiado uniformes, áreas negras/blancas/grises muy grandes o archivos sospechosamente pequeños para su resolución.

Estos criterios son heurísticos. Pueden ajustarse según el tipo de imágenes que se estén revisando.

---

## Seguridad

La herramienta está pensada para uso local.

- No sube imágenes a internet.
- No usa APIs externas.
- No modifica imágenes originales.
- No sobrescribe archivos originales.
- No borra archivos sin confirmación explícita.
- Prioriza mover archivos a `trash/` antes que eliminarlos definitivamente.

Esto permite revisar y descartar imágenes con menor riesgo de pérdida accidental.

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
    ├── image_preview.py
    ├── file_actions.py
    ├── report.py
    ├── settings.py
    └── ui.py
```

---

## Futuras mejoras

- Empaquetar como `.exe` con PyInstaller.
- Agregar configuración editable desde la interfaz.
- Mejorar la detección de blur con OpenCV.
- Agregar soporte opcional para más formatos.
- Guardar historial de análisis.
- Exportar reportes en HTML.
- Restaurar archivos movidos a `trash/` desde la app.
- Integrarlo con crawlers de imágenes para validar descargas automáticamente.

---

## Estado del proyecto

MVP funcional para revisión local de imágenes.
