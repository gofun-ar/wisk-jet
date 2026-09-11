# Auditoría Jet — tablero

Tablero de control de inventario y desviación del local Jet, alimentado con los
reportes de Desviación de Wisk entre conteos de inventario de Nancy Díaz.

## Contenido

- `index.html` — el tablero. Archivo único, sin dependencias externas salvo la
  tipografía. Se publica por GitHub Pages y se embebe en Notion.
- `actualizar_dashboard.py` — convierte un JSON de `get_variance` del conector
  Wisk en la fila semanal del tablero.

## Alcance

Este repositorio contiene **únicamente** el local Jet. Cada local va en su propio
repositorio y su propio sitio: GitHub Pages publica el sitio de forma pública
aunque el repositorio sea privado, así que compartir repositorio equivale a
compartir los datos de todos los locales alojados en él.

## Ciclo semanal

1. En una sesión de Claude con el conector Wisk, identificar los dos conteos
   consecutivos de Nancy Díaz con `list_inventories`.
2. Correr `get_variance` con esos dos IDs: una llamada para el total del local y
   una por zona.
3. Correr `actualizar_dashboard.py` con esos JSON. El script calcula ventas,
   costo de mercadería, costo real, costo objetivo, encogimiento, agotamientos,
   desviación reportada y diferencia real, y agrega la fila al `index.html`.
4. Revisar el aviso del script: si la diferencia real supera el 2% del consumo,
   investigar antes de publicar.
5. Actualizar a mano el encabezado de la última semana y el gráfico por barra.
6. Commit y push. GitHub Pages republica solo.

## Cómo se calcula la diferencia real

La desviación que informa Wisk incluye el diferencial de costo entre códigos
duplicados del maestro de artículos, que no es pérdida de mercadería. La
diferencia real es esa desviación menos los ítems que pertenecen a los grupos de
varianza configurados en el venue (gaseosas, Red Bull, agua, BritviC). Es la
misma definición para toda la serie, de modo que las semanas son comparables
entre sí.

## Advertencia sobre las cifras

Cada semana queda registrada con los valores vigentes al cerrarla. Si más tarde
se corrige una carga en Wisk, el sistema recalcula ese período y puede mostrar
cifras distintas de las publicadas acá. Al armar esta serie se detectaron dos
semanas en esa situación.
