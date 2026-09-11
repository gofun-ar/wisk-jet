#!/usr/bin/env python3
"""
Regenera el bloque DATOS del dashboard de Jet a partir de los JSON que devuelve
el conector Wisk (get_variance).

Uso:
    python3 actualizar_dashboard.py \
        --html jet-dashboard.html \
        --total  /ruta/get_variance_TOTAL.json \
        --zona "Barra 1=/ruta/var_barra1.json" \
        --zona "Barra 2=/ruta/var_barra2.json" \
        ... \
        --etiqueta "8 - 15 sep" \
        --objetivo 20.31 --encogimiento -1.55

El script no consulta Wisk por sí mismo: el conector es MCP y se llama desde una
sesión de Claude. Esa sesión puede ser una tarea programada, con lo cual el ciclo
completo corre desatendido: la tarea llama a get_variance, guarda los JSON y
ejecuta este script.

Qué calcula
-----------
- Ventas, COGS y costo real: de stats_high_level.
- Costo objetivo, encogimiento y agotamientos del período: de stats.variance
  y stats.consumption. NO hay que cargarlos a mano.
- Desviación reportada: suma de cost_difference de todos los ítems.
- Diferencia real: lo anterior menos los ítems que pertenecen a los grupos de
  varianza configurados en el venue (variance_groups). Esa es la definición
  homogénea usada en toda la serie.
- Por zona: lo mismo sobre cada JSON de zona, expresado en % del consumo.

Todo lo que el dashboard necesita sale del JSON. No hay carga manual.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def cargar(ruta):
    """Los resultados del conector vienen envueltos en [{'text': '<json>'}]."""
    bruto = json.loads(Path(ruta).read_text())
    if isinstance(bruto, list) and bruto and "text" in bruto[0]:
        return json.loads(bruto[0]["text"])
    return bruto


def ids_de_grupos(doc):
    ids = set()
    for g in doc.get("variance_groups") or []:
        ids |= set(g.get("item_ids") or [])
    return ids


def resumir(doc, grupos):
    total = agrupado = consumo = 0.0
    for b in doc.get("bottles") or []:
        v = b["stats"]["variance"]["dollars"]["cost_difference"]
        total += v
        consumo += b["stats"]["consumption"]["consumption"].get("dollars") or 0
        if b["bottle"]["id"] in grupos:
            agrupado += v
    return {"reportada": total, "grupos": agrupado, "limpia": total - agrupado,
            "consumo": consumo}


def mes_de(doc):
    MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    return MESES[int(doc["interval"]["end"][5:7]) - 1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--html", required=True)
    p.add_argument("--total", required=True)
    p.add_argument("--zona", action="append", default=[],
                   help='Formato "Nombre=/ruta.json". Repetir por zona.')
    p.add_argument("--etiqueta", required=True, help='Ej. "8 - 15 sep"')
    p.add_argument("--solo-mostrar", action="store_true",
                   help="Calcula e imprime, sin tocar el HTML.")
    a = p.parse_args()

    doc = cargar(a.total)
    grupos = ids_de_grupos(doc)
    if not grupos:
        sys.exit("El JSON no trae variance_groups. Sin ellos no se puede calcular "
                 "la diferencia real de forma homogénea.")

    r = resumir(doc, grupos)
    s = doc["stats_high_level"]
    st = doc["stats"]
    objetivo = st["variance"]["beverage_cost"]["theoretical"] * 100
    encogimiento = st["variance"]["shrinkage"]["percentage"] * 100
    agotamientos = st["consumption"]["depletions"]["dollars"]
    iv = doc["interval"]

    print(f"Período leído del conector: {iv['start_formatted']} → {iv['end_formatted']}")
    print(f"Cálculo generado por Wisk:  {doc.get('generated_at')}")
    print(f"Ítems en grupos de varianza: {len(grupos)}\n")
    print(f"  Ventas            ${s['sales_dollars']:>16,.0f}")
    print(f"  Costo mercadería  ${s['consumption_dollars']:>16,.0f}")
    print(f"  Costo real         {s['beverage_cost']*100:>16.2f}%")
    print(f"  Costo objetivo     {objetivo:>16.2f}%")
    print(f"  Encogimiento       {encogimiento:>16.2f}%")
    print(f"  Agotamientos      ${agotamientos:>16,.0f}")
    print(f"  Desviación        ${r['reportada']:>16,.0f}")
    print(f"  Códigos duplicados ${r['grupos']:>15,.0f}")
    print(f"  Diferencia real   ${r['limpia']:>16,.0f}"
          f"  ({r['limpia']/s['consumption_dollars']*100:.2f}% del consumo)")

    if r["limpia"] / s["consumption_dollars"] > 0.02:
        print("\n  ATENCIÓN: la diferencia real supera el 2% del consumo. "
              "Investigar antes de publicar.")

    zonas = []
    for z in a.zona:
        nombre, _, ruta = z.partition("=")
        rz = resumir(cargar(ruta), grupos)
        pc = rz["limpia"] / rz["consumo"] * 100 if rz["consumo"] else 0
        zonas.append((nombre, rz["limpia"], rz["consumo"], pc))

    if zonas:
        print("\n  Por zona (diferencia real sobre consumo)")
        suma = 0
        for n, limpia, consumo, pc in zonas:
            suma += limpia
            print(f"    {n:<22} ${limpia:>12,.0f}  {pc:>7.2f}%")
        desc = suma - r["limpia"]
        print(f"    {'Σ zonas vs local':<22} ${desc:>12,.0f} de descuadre "
              f"({abs(desc)/max(abs(r['limpia']),1)*100:.1f}%)")

    fila = (f' {{id:"{a.etiqueta}", mes:"{mes_de(doc)}", '
            f'ventas:{s["sales_dollars"]:.0f}, cogs:{s["consumption_dollars"]:.0f}, '
            f'real:{s["beverage_cost"]*100:.2f}, obj:{objetivo:.2f}, '
            f'desv:{r["reportada"]:.0f}, limpia:{r["limpia"]:.0f}, '
            f'enc:{encogimiento:.2f}, agot:{agotamientos:.0f}}}')

    print("\n  Fila para el bloque SEMANAS:\n")
    print("   " + fila + ",")

    if a.solo_mostrar:
        return

    ruta = Path(a.html)
    html = ruta.read_text()
    ancla = "\n];\n\nconst BARRAS4"
    if ancla not in html:
        sys.exit("No encontré el final del bloque SEMANAS en el HTML.")
    if f'id:"{a.etiqueta}"' in html:
        sys.exit(f'La semana "{a.etiqueta}" ya está cargada. Borrala antes de repetir.')
    html = html.replace(ancla, ",\n" + fila + ancla, 1)
    ruta.write_text(html)
    print(f"\n  Agregada al final de SEMANAS en {ruta.name}.")
    print("  Falta actualizar a mano: el encabezado de la última semana y el "
          "gráfico agrupado por barra (BARRAS4).")


if __name__ == "__main__":
    main()
