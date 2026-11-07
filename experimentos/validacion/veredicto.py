"""¿Sirve el veredicto de los revisores? Aciertos, unidades y CLV de la apuesta del día por cada palabra.

Cuenta la última revisión lista antes del inicio. «Contados» es la apuesta del día que cuenta para los aciertos (una
por día); «todos», cualquier apuesta del día que tuvo veredicto, aunque luego la reemplazara otra. Con pocas apuestas
no prueba nada: se mira cuando haya unas 30 contadas.

Solo lee la base de datos. Uso: .venv/bin/python experimentos/validacion/veredicto.py
"""

from sqlalchemy import text

from apuestas.db.session import session_scope
from apuestas.services import verdict


def main() -> None:
    with session_scope() as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        out = verdict.measure(s)
    for group, words in out.items():
        n = sum(r["settled"] for r in words.values())
        print(f"{group} ({n} liquidadas)")
        for word in verdict.WORDS:
            r = words.get(word)
            if r is None:
                print(f"  {word:<9} sin apuestas")
                continue
            print(f"  {word:<9} {r['hits']} ganadas, {r['misses']} perdidas, {r['pushes']} devueltas, "
                  f"{r['pending']} pendientes · {r['profit_units']:+.2f} u · CLV "
                  f"{'—' if r['avg_clv'] is None else format(r['avg_clv'], '+.1%')}")
    if sum(r["settled"] for r in out["contados"].values()) < 30:
        print("\nTodavía son menos de 30 apuestas contadas: no saques conclusiones.")


if __name__ == "__main__":
    main()
