"""¿Sirve la mesa de apostadores? Aciertos, unidades y CLV de la apuesta del día por cada resultado, y los pesos.

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
    for group in ("contados", "todos"):
        outcomes = out[group]
        n = sum(r["settled"] for r in outcomes.values())
        print(f"{group} ({n} liquidadas)")
        for outcome in verdict.OUTCOMES:
            r = outcomes.get(outcome)
            if r is None:
                print(f"  {outcome:<12} sin apuestas")
                continue
            print(f"  {outcome:<12} {r['hits']} ganadas, {r['misses']} perdidas, {r['pushes']} devueltas, "
                  f"{r['pending']} pendientes · {r['profit_units']:+.2f} u · CLV "
                  f"{'—' if r['avg_clv'] is None else format(r['avg_clv'], '+.1%')}")
    print("\nPesos de la mesa (empiezan en ×1; tope ×2, piso ×0,5):")
    for agent, weight in out["pesos"].items():
        print(f"  {verdict.AGENTS[agent][0]:<22} ×{weight:.3f}")
    if sum(r["settled"] for r in out["contados"].values()) < 30:
        print("\nTodavía son menos de 30 apuestas contadas: no saques conclusiones.")


if __name__ == "__main__":
    main()
