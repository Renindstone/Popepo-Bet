"""Normalización de nombres para relacionar equipos/jugadores entre fuentes."""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

_STOP = {
    "fc", "cf", "afc", "sc", "ac", "as", "ssc", "cd", "ud", "sd", "rcd", "ca", "rc", "club", "de", "the",
    "1", "sv", "tsg", "vfb", "vfl", "fsv", "bsc", "sk", "fk", "nk", "if", "bk", "calcio", "1899", "1846",
    "1904", "1909", "1910", "05", "04", "96", "98", "and", "hove", "albion",
}

# Variantes conocidas -> forma canónica (ya normalizada). La forma canónica es la de FotMob normalizada.
_TEAM_SEEDS = {
    # Inglaterra
    "man city": "manchester city", "man united": "manchester united", "man utd": "manchester united",
    "nottm forest": "nottingham forest", "nott forest": "nottingham forest", "wolves": "wolverhampton wanderers",
    "tottenham": "tottenham hotspur", "spurs": "tottenham hotspur", "west ham": "west ham united",
    "newcastle": "newcastle united", "brighton": "brighton", "bournemouth": "bournemouth",
    "leeds": "leeds united", "leicester": "leicester city", "ipswich": "ipswich town", "sheffield united":
    "sheffield united", "sheffield weds": "sheffield wednesday", "west brom": "west bromwich", "qpr":
    "queens park rangers", "coventry": "coventry city", "norwich": "norwich city", "stoke": "stoke city",
    "hull": "hull city", "luton": "luton town", "swansea": "swansea city", "cardiff": "cardiff city",
    "birmingham": "birmingham city", "derby": "derby county", "oxford": "oxford united", "wrexham": "wrexham",
    # Alemania
    "bayern munich": "bayern munchen", "bayern": "bayern munchen", "dortmund": "borussia dortmund",
    "mgladbach": "borussia monchengladbach", "borussia mgladbach": "borussia monchengladbach",
    "borussia m gladbach": "borussia monchengladbach", "monchengladbach": "borussia monchengladbach",
    "ein frankfurt": "eintracht frankfurt", "frankfurt": "eintracht frankfurt", "leverkusen": "bayer leverkusen",
    "rasenballsport leipzig": "rb leipzig", "leipzig": "rb leipzig", "rb leipzig": "rb leipzig",
    "koln": "koln", "cologne": "koln", "fc cologne": "koln", "hamburg": "hamburger", "hamburger sv": "hamburger",
    "hertha": "hertha berlin", "hertha bsc": "hertha berlin", "union berlin": "union berlin",
    "st pauli": "st pauli", "greuther furth": "greuther furth", "furth": "greuther furth",
    "fortuna dusseldorf": "fortuna dusseldorf", "dusseldorf": "fortuna dusseldorf",
    # España
    "ath madrid": "atletico madrid", "atl madrid": "atletico madrid", "atletico": "atletico madrid",
    "ath bilbao": "athletic", "athletic bilbao": "athletic", "betis": "real betis", "celta": "celta vigo",
    "sociedad": "real sociedad", "vallecano": "rayo vallecano", "espanol": "espanyol", "la coruna":
    "deportivo la coruna", "deportivo": "deportivo la coruna", "sp gijon": "sporting gijon", "oviedo":
    "real oviedo", "zaragoza": "real zaragoza", "santander": "racing santander", "racing": "racing santander",
    "alaves": "alaves", "leganes": "leganes", "almeria": "almeria", "cadiz": "cadiz", "granada": "granada",
    # Resto de Europa (rivales de Champions)
    "paris sg": "paris saint germain", "psg": "paris saint germain", "marseille": "marseille",
    "olympique marseille": "marseille", "lyon": "lyon", "olympique lyonnais": "lyon", "sp lisbon":
    "sporting cp", "sporting lisbon": "sporting cp", "sporting": "sporting cp", "benfica": "benfica",
    "porto": "porto", "sp braga": "braga", "inter": "inter", "internazionale": "inter", "inter milan": "inter",
    "milan": "milan", "ac milan": "milan", "juventus": "juventus", "napoli": "napoli", "roma": "roma",
    "atalanta": "atalanta", "lazio": "lazio", "psv eindhoven": "psv", "psv": "psv", "ajax": "ajax",
    "feyenoord": "feyenoord", "az alkmaar": "az", "club brugge": "club brugge", "brugge": "club brugge",
    "galatasaray": "galatasaray", "fenerbahce": "fenerbahce", "besiktas": "besiktas", "celtic": "celtic",
    "rangers": "rangers", "olympiakos": "olympiacos", "olympiacos": "olympiacos",
    # Mismo club con otro nombre en football-data (revisados a mano; ver ingest/dedupe.py). Ojo: "AEK" es el
    # de Atenas (liga griega); "AEK Larnaca" (Chipre) y "Aris Limassol" son otros clubes.
    "aek": "aek athens", "paok": "paok thessaloniki", "antwerp": "royal antwerp", "nijmegen": "nec nijmegen",
    "nec": "nec nijmegen", "guimaraes": "vitoria guimaraes", "saint gilloise": "union saint gilloise",
    "union sg": "union saint gilloise", "verona": "hellas verona", "clermont": "clermont foot",
    "hearts": "heart of midlothian", "buyuksehyr": "basaksehir",
    # Ligas extra de football-data (izquierda) frente a FotMob (derecha)
    "rapid": "rapid wien", "copenhagen": "kobenhavn", "aarhus": "agf", "jagiellonia": "jagiellonia bialystok",
    "legia": "legia warszawa", "rakow": "rakow czestochowa", "univ craiova": "universitatea craiova",
}

# Letras que NFKD no descompone ("Bodø" -> "bodo", "Kraków" sí se descompone solo)
_TRANSLIT = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ß": "ss",
                           "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ı": "i", "þ": "th", "ð": "d"})


def strip_accents(text: str) -> str:
    text = text.translate(_TRANSLIT)
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalize(name: str) -> str:
    s = strip_accents(name).lower().replace("&", " and ")
    s = re.sub(r"['’`´]", "", s)
    s = re.sub(r"[.\-/()]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    tokens = ["saint" if t == "st" else t for t in s.split() if t and t not in _STOP]  # "St Etienne" = "Saint-Étienne"
    return " ".join(tokens)


def team_key(name: str) -> str:
    """Clave canónica de un equipo para comparar entre fuentes."""
    n = normalize(name)
    if n in _TEAM_SEEDS:
        return _TEAM_SEEDS[n]
    # Probar quitando prefijos/sufijos frecuentes ("united", "city" no: son distintivos)
    return n


# Palabras que pueden faltar sin cambiar de club ("Alaves" = "Deportivo Alaves", "Hull" = "Hull City").
# "united" NO está: "Dundee" y "Dundee United" son clubes distintos.
_WEAK_EXTRA = {
    "deportivo", "real", "club", "hotspur", "athletic", "sporting", "olympique", "calcio", "town", "city",
    "wanderers", "cp", "sad", "sc", "football",
}


def similarity(a: str, b: str) -> float:
    """0-100. Penaliza palabras distintivas de más ("Paris" vs "Paris Saint Germain")."""
    ka, kb = team_key(a), team_key(b)
    if ka == kb:
        return 100.0
    ta, tb = set(ka.split()), set(kb.split())
    base = float(fuzz.token_sort_ratio(ka, kb))
    if ta and tb and (ta <= tb or tb <= ta):
        extra = ta ^ tb
        return max(base, 92.0) if extra <= _WEAK_EXTRA else min(base, 75.0)
    return base


def contained(a: str, b: str) -> bool:
    """Las palabras de un nombre están todas en el otro ("Inter" en "Inter Milano", "Lens" en "Racing Club de Lens")."""
    ta, tb = set(team_key(a).split()), set(team_key(b).split())
    return bool(ta and tb and (ta <= tb or tb <= ta))


def best_match(name: str, candidates: dict[int, str], threshold: float = 80.0) -> tuple[int | None, float]:
    """Devuelve el id del candidato más parecido si supera el umbral."""
    best_id, best_score = None, 0.0
    for cid, cname in candidates.items():
        score = similarity(name, cname)
        if score > best_score:
            best_id, best_score = cid, score
    return (best_id, best_score) if best_score >= threshold else (None, best_score)


def person_key(name: str) -> str:
    return normalize(name)


def person_similarity(a: str, b: str) -> float:
    """Para nombres de personas: 'T Bramall' vs 'Thomas Bramall' deben coincidir."""
    na, nb = normalize(a).split(), normalize(b).split()
    if not na or not nb:
        return 0.0
    if na[-1] != nb[-1]:
        return fuzz.token_sort_ratio(" ".join(na), " ".join(nb)) * 0.8
    # Mismo apellido: comprobar inicial del nombre si existe
    if len(na) > 1 and len(nb) > 1 and na[0][0] != nb[0][0]:
        return 60.0
    return 95.0


def search_score(query: str, candidate: str) -> float:
    """Para búsquedas del usuario: 'Rayo' debe encontrar 'Rayo Vallecano', 'Barca' a 'Barcelona'."""
    kq, kc = team_key(query), team_key(candidate)
    if not kq:
        return 0.0
    if kq == kc:
        return 100.0
    tq, tc = set(kq.split()), set(kc.split())
    if tq <= tc:
        return 90.0 - 0.5 * len(tc - tq)
    if any(t.startswith(q) for q in tq for t in tc if len(q) >= 4):
        return 82.0
    return max(similarity(query, candidate), float(fuzz.partial_ratio(kq, kc)) * 0.85)
