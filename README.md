# Image Quality Reviewer

Una aplicación de escritorio local para revisar carpetas de imágenes y detectar archivos problemáticos descargados automáticamente desde internet.

El objetivo principal es encontrar imágenes que probablemente estén rotas, corruptas, truncadas o inutilizables, sin comprometer imágenes sanas. La herramienta está pensada para trabajar con carpetas grandes de imágenes y ayudar a revisar casos dudosos antes de moverlos a una carpeta local `trash/`.

---

## Objetivo

El proyecto busca detectar imágenes problemáticas como:

- archivos que no existen o están vacíos;
- archivos que no son imágenes reales;
- imágenes que Pillow no puede abrir o decodificar;
- JPEGs truncados o sin marcador final `FF D9`;
- PNGs incompletos o sin chunk `IEND`;
- WEBP o BMP con tamaños declarados inconsistentes;
- imágenes parcialmente descargadas;
- imágenes corruptas por bytes dañados;
- imágenes visualmente dañadas, con glitches, ruido extremo o cortes artificiales.

La aplicación prioriza una regla importante:

> Si hay duda, la imagen no debe eliminarse automáticamente.

---

## Qué NO debería rechazar automáticamente

Una imagen no debe marcarse como mala solo por tener:

- fondo blanco;
- fondo negro;
- fondo liso;
- baja textura;
- blur;
- pared;
- cielo;
- cartel detrás;
- banner;
- packaging;
- pantalla;
- tela;
- márgenes;
- objetos detrás de una persona;
- zonas uniformes que forman parte real de la imagen.

Estos casos pueden ser imágenes perfectamente válidas. Por eso la app separa problemas técnicos fuertes de señales visuales dudosas.

---

## Estado actual del proyecto

El proyecto tiene dos capas de detección:

1. **Validaciones determinísticas**
2. **Clasificador entrenable con IA**

Las validaciones determinísticas son las más confiables. Detectan problemas técnicos reales del archivo, como archivos vacíos, imágenes que no se pueden abrir, errores de decodificación o estructuras incompletas.

El clasificador de IA es una capa adicional para intentar detectar corrupción visual compleja. Esta parte todavía requiere calibración con datos reales, porque puede cometer errores: puede saltear imágenes rotas importantes o marcar como dudosas algunas imágenes sanas.

Por ahora, el modelo debe usarse como apoyo para revisión, no como única fuente de verdad.

---

## Tecnologías usadas

- Python
- Tkinter
- Pillow
- OpenCV
- NumPy
- PyTorch
- Torchvision
- Hugging Face Datasets

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
├── models/
│   └── .gitkeep
│
├── reports/
│   └── .gitkeep
│
├── trash/
│   └── .gitkeep
│
├── training_data/
│   ├── ok/
│   │   └── .gitkeep
│   └── broken/
│       └── .gitkeep
│
├── scripts/
│   ├── download_broken_from_huggingface.py
│   ├── generate_synthetic_broken_images.py
│   └── train_corruption_classifier.py
│
└── src/
    ├── __init__.py
    ├── scanner.py
    ├── image_analysis.py
    ├── ml_corruption_classifier.py
    ├── image_preview.py
    ├── file_actions.py
    ├── report.py
    ├── settings.py
    └── ui.py
```

---

## Instalación

Crear y activar entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

Instalar dependencias:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Dependencias principales

El archivo `requirements.txt` debería incluir algo similar a:

```txt
Pillow==10.4.0
numpy>=1.26,<3
opencv-python>=4.10,<5
torch>=2.3,<3
torchvision>=0.18,<1
datasets>=2.20,<4
```

---

## Uso de la aplicación

Ejecutar:

```powershell
python main.py
```

Luego:

1. Seleccionar una carpeta de imágenes.
2. Ejecutar el escaneo.
3. Revisar los archivos detectados.
4. Previsualizar cada imagen.
5. Marcar o desmarcar manualmente.
6. Mover archivos seleccionados o marcados a `trash/`.
7. Generar un reporte si hace falta.

---

## Clasificación de resultados

La app clasifica cada imagen en distintos estados.

### OK

La imagen parece sana.

### Info

La imagen tiene información útil, pero no debería revisarse ni rechazarse automáticamente.

Ejemplos:

- baja resolución;
- posible blur;
- modelo de IA no disponible.

### Review / Warning

La imagen tiene señales leves, pero no suficiente evidencia para marcarla como mala.

Ejemplos:

- formato no soportado;
- extensión distinta al formato detectado;
- tamaño de archivo sospechosamente bajo.

### Suspect

La imagen es dudosa y debería revisarse o volver a descargarse.

Ejemplos:

- el modelo de IA detecta probabilidad alta de corrupción;
- el archivo tiene señales técnicas débiles y señales visuales dudosas;
- el caso no es suficientemente seguro como para descartarlo automáticamente.

### Broken

La imagen tiene evidencia fuerte de estar rota.

Ejemplos:

- archivo vacío;
- archivo que no existe;
- no es una imagen real;
- error de decodificación;
- estructura inválida fuerte;
- modelo de IA con probabilidad extremadamente alta, si se decidió confiar en ese umbral.

---

## Seguridad

La aplicación no borra archivos de forma permanente automáticamente.

Cuando se decide mover una imagen, el archivo se mueve a:

```text
trash/
```

Antes de mover archivos, la app pide confirmación.

---

## Cómo funciona la detección actual

### 1. Validaciones determinísticas

Estas validaciones son las más importantes y confiables:

- el archivo existe;
- el archivo no está vacío;
- el archivo tiene un tamaño mínimo razonable;
- Pillow puede reconocer la imagen;
- Pillow puede decodificar la imagen completa;
- JPEG tiene marcador final `FF D9`;
- PNG tiene chunk final `IEND`;
- WEBP y BMP no declaran tamaños imposibles;
- dimensiones válidas;
- formato y extensión coinciden.

Estas reglas se mantienen aunque el modelo de IA no exista.

### 2. Clasificador de IA

El clasificador de IA intenta aprender la diferencia entre:

```text
training_data/ok/
training_data/broken/
```

Usa un modelo preentrenado de `torchvision` y lo ajusta con ejemplos propios.

El modelo se guarda en:

```text
models/image_corruption_classifier.pt
```

Si ese archivo no existe, la app sigue funcionando con los hard checks, pero no usa IA.

---

## Guía para entrenar el modelo

### Paso 1: preparar carpetas

Crear estas carpetas si no existen:

```powershell
New-Item -ItemType Directory -Force training_data\ok, training_data\broken, models
```

### Paso 2: agregar imágenes sanas

En `training_data/ok/` colocar imágenes que NO deben ser marcadas como malas.

Es muy importante incluir ejemplos difíciles, como:

- personas con fondos desenfocados;
- carteles detrás;
- paredes;
- telas;
- fondos blancos;
- fondos negros;
- cielo;
- packaging;
- pantallas;
- objetos detrás;
- imágenes con márgenes;
- imágenes con zonas lisas reales.

Esta carpeta es clave para reducir falsos positivos.

### Paso 3: agregar imágenes rotas

En `training_data/broken/` colocar ejemplos reales de imágenes dañadas:

- glitches;
- descargas incompletas;
- ruido artificial;
- bandas de error;
- imágenes truncadas;
- colores corruptos;
- partes reemplazadas por bloques artificiales.

### Paso 4: generar corruptas sintéticas opcionales

Si tenés pocas imágenes rotas reales, podés generar ejemplos sintéticos a partir de imágenes sanas:

```powershell
python scripts\generate_synthetic_broken_images.py
```

Esto crea variantes rotas en:

```text
training_data/broken/
```

Ejemplos de corrupciones sintéticas:

- truncamiento inferior;
- paneles de color;
- bandas horizontales;
- bandas verticales;
- bloques de color;
- pixeles calientes;
- canales RGB rotos;
- degradación JPEG fuerte;
- desplazamiento de canales.

Estas imágenes sirven como apoyo, pero no reemplazan a las corruptas reales.

### Paso 5: descargar ejemplos desde Hugging Face opcionalmente

Si se quiere sumar material externo:

```powershell
python scripts\download_broken_from_huggingface.py
```

Esto descarga imágenes en:

```text
training_data/broken/
```

Importante: muchas imágenes públicas son degradadas, no necesariamente rotas por descarga real. Conviene revisarlas antes de confiar demasiado en ellas.

### Paso 6: entrenar

```powershell
python scripts\train_corruption_classifier.py
```

El entrenamiento genera:

```text
models/image_corruption_classifier.pt
```

Después de eso, la app puede usar el modelo al ejecutar:

```powershell
python main.py
```

---

## Proporción recomendada de datos

No conviene entrenar solo con imágenes rotas.

Si se entrena con `broken/` lleno y `ok/` vacío o muy pobre, el modelo aprende que casi todo parece roto.

Una proporción inicial razonable:

```text
training_data/ok/      1000 a 3000 imágenes sanas reales
training_data/broken/   300 a 1500 imágenes rotas reales o sintéticas
```

Si el objetivo principal es evitar falsos positivos, la carpeta `ok/` debe ser muy fuerte y variada.

Mejor todavía:

```text
ok/
  muchas imágenes sanas difíciles

broken/
  corruptas reales
  corruptas sintéticas variadas
  algunas degradadas externas
```

---

## Qué revisar si el modelo funciona mal

Si el modelo saltea imágenes importantes o marca como dudosas imágenes buenas, no significa necesariamente que la idea no sirva. Significa que el dataset o los umbrales todavía no están bien calibrados.

### Si marca buenas como dudosas

Agregar a `training_data/ok/` más ejemplos parecidos a esas imágenes buenas:

- fondos desenfocados;
- carteles;
- paredes;
- telas;
- fondos lisos;
- packaging;
- pantallas;
- imágenes con sombras;
- imágenes con zonas de baja textura.

Después volver a entrenar.

### Si saltea imágenes rotas

Agregar esas imágenes salteadas a `training_data/broken/` y volver a entrenar.

También conviene generar corruptas sintéticas similares al error que no detectó.

### Si el modelo queda demasiado agresivo

Subir los thresholds en `src/settings.py`:

```python
ML_SUSPECT_THRESHOLD = 0.80
ML_BROKEN_THRESHOLD = 0.99
```

### Si el modelo queda demasiado permisivo

Bajar apenas el threshold de sospecha:

```python
ML_SUSPECT_THRESHOLD = 0.65
```

No conviene bajar demasiado `ML_BROKEN_THRESHOLD`, porque eso puede aumentar falsos positivos graves.

---

## Thresholds actuales recomendados

En `src/settings.py`:

```python
ML_SUSPECT_THRESHOLD = 0.70
ML_BROKEN_THRESHOLD = 0.97
```

Para un modo más conservador:

```python
ML_SUSPECT_THRESHOLD = 0.80
ML_BROKEN_THRESHOLD = 0.99
```

Para este proyecto, conviene ser conservador:

```text
más suspect, menos broken automático
```

---

## Recomendación importante sobre el modelo

El modelo de IA no debería ser usado como única decisión final al principio.

Una política más segura:

```text
hard checks técnicos -> Broken
modelo IA alto -> Suspect
modelo IA extremadamente alto -> Broken solo si fue validado con datos reales
```

En otras palabras: si el modelo todavía falla, usalo principalmente para traer imágenes a revisión, no para eliminarlas automáticamente.

---

## Flujo recomendado de mejora

1. Ejecutar la app sobre una carpeta real.
2. Revisar falsos positivos.
3. Mover esos falsos positivos a `training_data/ok/`.
4. Revisar falsos negativos.
5. Mover esos falsos negativos a `training_data/broken/`.
6. Volver a entrenar.
7. Repetir.

Este ciclo es más importante que usar un dataset público grande.

---

## Reportes

Los reportes se generan en:

```text
reports/
```

Incluyen:

- carpeta analizada;
- estado de cada imagen;
- score;
- dimensiones;
- blur score;
- motivos detectados;
- estado de marcado manual.

---

## Limitaciones actuales

Detectar imágenes visualmente corruptas sin falsos positivos es difícil.

Los hard checks técnicos son confiables, pero la detección visual requiere datos representativos. Un modelo entrenado con 4000 imágenes puede fallar si esas imágenes no cubren bien los casos difíciles.

Ejemplos de problemas posibles:

- el modelo aprende un solo tipo de corrupción;
- faltan imágenes sanas difíciles;
- hay demasiadas corruptas sintéticas de un solo estilo;
- hay pocas corruptas reales;
- las clases están desbalanceadas;
- el threshold es demasiado bajo;
- el modelo ve patrones que no representan el problema real.

Por eso, el dataset debe ir mejorando con ejemplos reales del uso de la app.

---

## Próximos pasos posibles

- agregar una pantalla para revisar falsos positivos y falsos negativos;
- guardar decisiones manuales para reentrenar;
- exportar imágenes `ok` y `broken` desde la propia app;
- agregar métricas de validación por clase;
- generar una matriz de confusión después de entrenar;
- separar `broken` en subclases: `truncated`, `glitch`, `noise`, `placeholder`, `color_panel`;
- entrenar con más datos reales;
- ajustar thresholds desde la interfaz;
- mantener `broken` automático solo para hard checks.

---

## Nota final

Esta herramienta es un apoyo para revisión local de imágenes.

No sube imágenes a internet, no modifica imágenes originales y no reemplaza una revisión humana.

La estrategia recomendada es usar la app de forma conservadora: detectar lo claramente roto, revisar lo dudoso y mejorar el modelo con ejemplos reales.
