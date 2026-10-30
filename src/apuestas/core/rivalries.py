"""Clásicos y derbis: rivalidades históricas de las ligas completas.

`ingest.store.ensure_rivalries` las copia a la tabla `rivalry` (con los equipos que ya existen; un equipo que sube
de categoría se enlaza en la siguiente sincronización). En ellos se ven más faltas y tarjetas de lo que espera el
modelo (`fitting.DERBY_FACTOR`, docs/modelos.md); los nombres de los equipos son los de la tabla `team`.
"""

RIVALRIES: list[tuple[str, str, str]] = [
    # Premier League
    ("Liverpool", "Everton", "Derbi de Merseyside"),
    ("Liverpool", "Manchester United", "Clásico del noroeste"),
    ("Manchester United", "Manchester City", "Derbi de Mánchester"),
    ("Arsenal", "Tottenham Hotspur", "Derbi del norte de Londres"),
    ("Chelsea", "Tottenham Hotspur", "Derbi de Londres"),
    ("Arsenal", "Chelsea", "Derbi de Londres"),
    ("Newcastle United", "Sunderland", "Derbi Tyne-Wear"),
    ("Crystal Palace", "Brighton & Hove Albion", "Derbi de la M23"),
    # LaLiga
    ("Real Madrid", "Barcelona", "El Clásico"),
    ("Real Madrid", "Atlético Madrid", "Derbi madrileño"),
    ("Real Betis", "Sevilla", "Derbi sevillano"),
    ("Athletic Club", "Real Sociedad", "Derbi vasco"),
    ("Barcelona", "Espanyol", "Derbi barcelonés"),
    ("Valencia", "Levante", "Derbi valenciano"),
    ("Valencia", "Villarreal", "Derbi de la Comunidad Valenciana"),
    ("Celta Vigo", "Deportivo A Coruña", "Derbi gallego"),
    # Bundesliga
    ("Bayern München", "Borussia Dortmund", "Der Klassiker"),
    ("Borussia Dortmund", "Schalke 04", "Derbi del Ruhr"),
    ("1. FC Köln", "Borussia Mönchengladbach", "Derbi renano"),
    ("Hamburger SV", "Werder Bremen", "Nordderby"),
    ("Eintracht Frankfurt", "Mainz 05", "Derbi del Rin-Meno"),
    # Serie A
    ("Inter", "Milan", "Derby della Madonnina"),
    ("Roma", "Lazio", "Derby della Capitale"),
    ("Juventus", "Torino", "Derby della Mole"),
    ("Juventus", "Inter", "Derby d'Italia"),
    ("Napoli", "Roma", "Derby del Sole"),
    ("Fiorentina", "Juventus", "Fiorentina-Juventus"),
    # Ligue 1
    ("Paris Saint-Germain", "Marseille", "Le Classique"),
    ("Lyon", "Saint-Étienne", "Derbi del Ródano"),
    ("Nice", "Monaco", "Derbi de la Costa Azul"),
    ("Lens", "Lille", "Derbi del Norte"),
    ("Rennes", "Nantes", "Derbi bretón"),
    ("Marseille", "Lyon", "Olympico"),
    ("Paris FC", "Paris Saint-Germain", "Derbi de París"),
    # Primeira Liga
    ("Benfica", "Sporting CP", "Derbi de Lisboa"),
    ("FC Porto", "Benfica", "O Clássico"),
    ("FC Porto", "Sporting CP", "Clássico Porto-Sporting"),
    ("Braga", "Vitória de Guimarães", "Derbi del Miño"),
    # Pro League
    ("Anderlecht", "Club Brugge", "Topper"),
    ("Club Brugge", "Cercle Brugge", "Derbi de Brujas"),
    ("Anderlecht", "Standard Liège", "Clásico belga"),
    ("Royal Antwerp", "Beerschot", "Derbi de Amberes"),
    # Süper Lig
    ("Galatasaray", "Fenerbahçe", "Derbi intercontinental"),
    ("Fenerbahçe", "Beşiktaş", "Derbi de Estambul"),
    ("Galatasaray", "Beşiktaş", "Derbi de Estambul"),
    ("Trabzonspor", "Fenerbahçe", "Trabzonspor-Fenerbahçe"),
]
