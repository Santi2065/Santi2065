<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/masthead-dark.svg">
  <img alt="Santiago Groba Alonso — desarrollador de software e IA, en producción desde 2020" src="assets/masthead-light.svg" width="100%">
</picture>

Soy **Santi**. Estudio Ingeniería en Inteligencia Artificial en la UdeSA y desde 2020 trabajo por mi cuenta para escribanías y pymes. Empecé administrando su infraestructura y hoy desarrollo y opero sistemas en producción: desde un comparador de 1.182 casas de cambio en Colombia hasta un LLM que vive en el servidor de una escribanía.

[LinkedIn](https://linkedin.com/in/santiago-groba) · [preciodeldolar.com.co](https://preciodeldolar.com.co) · CABA, Argentina · español, inglés y un poco de francés

## En qué trabajo

<a href="https://preciodeldolar.com.co"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/proof-pdc-dark.svg"><img align="right" width="46%" alt="1.182 casas de cambio en 62 ciudades; las cinco con más casas: Bogotá 226, Ipiales 207, Medellín 150, Cartagena 101, Cúcuta 97" src="assets/proof-pdc-light.svg"></picture></a>

### PrecioDelDolarCo

Comparador de tasas de cambio en Colombia, en producción en [preciodeldolar.com.co](https://preciodeldolar.com.co). Compara tasas de compra y venta y lista 1.182 casas de cambio en 62 ciudades.

- Scraper con 80 fuentes y 13 parsers
- Panel para dueños de casas de cambio, con planes pagos

`Next.js` · `PostgreSQL` · `Puppeteer`

<br clear="right">

<picture><source media="(prefers-color-scheme: dark)" srcset="assets/proof-llm-dark.svg"><img align="left" width="46%" alt="Segundos por respuesta: antes unos 10, ahora unos 3; 27B parámetros, FP8, dos GPU RTX 3090" src="assets/proof-llm-light.svg"></picture>

### LLM on-premise

Para el archivo de escrituras de una escribanía: Qwen3.8 de 27B parámetros en FP8, sobre dos RTX 3090 y adentro de la oficina: los documentos y las consultas se procesan ahí. Cada respuesta tarda unos 3 segundos; antes tardaba unos 10.

`vLLM` · `Qdrant` · `PostgreSQL` · `RAG`

<br clear="left">

<a href="https://github.com/joacocullen/cot-compress"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/proof-research-dark.svg"><img align="right" width="46%" alt="Esquema de qué viaja del turno T1 al T2: preservar todo, comprimir a un resumen o descartar y dejar solo la respuesta" src="assets/proof-research-light.svg"></picture></a>

### Investigación: CoT-Compress

¿Conviene preservar o descartar el razonamiento de un LLM entre turnos? Un chat local que comprime el razonamiento del modelo y lo reinyecta como memoria, con 6 estrategias de compresión y pruebas exploratorias propias sobre Terminal-Bench 2.0.

Dirigido por Juan Wisznia (UdeSA). Paper en preparación.

[joacocullen/cot-compress](https://github.com/joacocullen/cot-compress)

<br clear="right">

<picture><source media="(prefers-color-scheme: dark)" srcset="assets/proof-infra-dark.svg"><img align="left" width="46%" alt="Desde 2020: soporte remoto de equipos; redes, backups y acceso remoto; renovación de hardware; monitoreo con Tactical RMM" src="assets/proof-infra-light.svg"></picture>

### Infraestructura

Escribanías y pymes de CABA, desde 2020. Ahí empecé: soporte remoto de equipos, redes, backups y acceso remoto, renovación de hardware y monitoreo con Tactical RMM.

<br clear="left">

<a href="https://github.com/Santi2065?tab=repositories"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/plate-dark.svg"><img alt="22 trabajos documentados entre 2022 y 2026, uno por punto en la línea de tiempo" src="assets/plate-light.svg" width="100%"></picture></a>

## Facultad

Ingeniería en Inteligencia Artificial en la UdeSA. Los trabajos con repositorio tienen su README con figuras y resultados reproducibles.

| Trabajo | Qué es | Resultado |
|---|---|---|
| **DermaVision**<br><sub>Visión artificial · 2026</sub> | Clasifica 7 tipos de lesiones de piel sobre 10.015 imágenes dermatoscópicas | 0,729 de macro-F1 |
| **[Estéreo&nbsp;3D](https://github.com/Santi2065/stereo-3d-reconstruction)**<br><sub>Visión artificial · 2026</sub> | Reconstrucción 3D estéreo de una estatua de cerámica | 21 de 21 pares registrados, 3,3 M de puntos |
| **[Plataforma&nbsp;de&nbsp;pozos](https://github.com/joaco1212004/Ingenieria_de_Software---Groba-Salomon-Di_Cola)**<br><sub>Ingeniería de software · 2026</sub> | Pronóstico a 60 meses de 4.929 pozos con un modelo Arps + LSTM | — |
| **ClearWave**<br><sub>Aprendizaje automático · 2025</sub> | Elimina el ruido de la voz con autoencoders y una U-Net | — |
| **[Agente&nbsp;de&nbsp;Hex](https://github.com/Santi2065/hex-alpha-beta-agent)**<br><sub>Fundamentos de IA · 2025</sub> | Agente de Hex con búsqueda alfa-beta y caminos mínimos (A*) | 18 de 18 partidas ganadas a los agentes base |
| **[Simulador&nbsp;ARMv8](https://github.com/Santi2065/armv8-simulator)**<br><sub>Arquitectura de computadoras · 2025</sub> | Simulador funcional de ARMv8 (A64) en C | 11 de 11 programas iguales al simulador de referencia |
| **[File&nbsp;system&nbsp;V6](https://github.com/Santi2065/unix-v6-filesystem)**<br><sub>Sistemas operativos · 2025</sub> | Lector del file system de Unix V6 en C | Salida idéntica a la de referencia en 12 de 12 pruebas |

[Ver todos los repositorios](https://github.com/Santi2065?tab=repositories)

## Herramientas

**Lenguajes** · Python · TypeScript · C · C++ · Java<br>
**IA y ML** · PyTorch · vLLM · llama.cpp · Ollama · Qdrant · MLflow<br>
**Datos** · PostgreSQL · dbt · Dagster<br>
**Web** · Next.js · React · FastAPI<br>
**Infra** · Docker · Linux · AWS · nginx · Prometheus · Grafana · GitHub Actions

<sub>Las figuras salen de datos reales y se generan con [`scripts/build_profile.py`](scripts/build_profile.py).</sub>
