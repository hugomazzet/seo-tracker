"""Rapport HTML (graphiques Plotly) à partir du CSV des positions.

Le fichier généré est autonome : il s'ouvre dans n'importe quel navigateur,
sans connexion internet ni serveur.
"""

import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlparse

import plotly.graph_objects as go

# En dessous de ce nombre d'impressions, la position moyenne est peu fiable
LOW_IMPRESSIONS = 10
# Écart de référence (en jours) pour la colonne "Évolution"
TREND_DAYS = 7
# La page 1 de Google correspond aux positions 1 à 10
PAGE_ONE_LAST = 10
# Granularités de la courbe de position : (clé, libellé, format des dates de l'axe,
# graduation de l'axe : None = automatique, "M1" = un repère par mois)
GRANULARITIES = [
    ("day", "Jour", "%d/%m", None),
    ("week", "Semaine", "%d/%m", None),
    ("month", "Mois", "%m/%Y", "M1"),
]
# À partir de ce nombre de jours relevés, la vue Semaine est affichée par défaut
WEEK_DEFAULT_MIN_DAYS = 14
# Couleurs des mots clés (identiques quelle que soit la granularité)
COLORS = [
    "#636efa", "#ef553b", "#00cc96", "#ab63fa", "#ffa15a",
    "#19d3f3", "#ff6692", "#b6e880", "#ff97ff", "#fecb52",
]

# Bascule de granularité : on garde la sélection du mot clé masqué dans la légende
GRANULARITY_SCRIPT = """
(function () {
  var gd = document.getElementById("positions-chart");
  var buttons = document.querySelectorAll(".gran button");
  var hidden = {};

  function current() {
    return document.querySelector(".gran button.active").dataset.gran;
  }

  function show(button) {
    var gran = button.dataset.gran;
    var previous = current();
    gd.data.forEach(function (t) {
      if (t.meta === previous) { hidden[t.name] = (t.visible === "legendonly"); }
    });
    var visible = [];
    var legend = [];
    gd.data.forEach(function (t) {
      var on = t.meta === gran;
      visible.push(on ? (hidden[t.name] ? "legendonly" : true) : false);
      legend.push(on);
    });
    Plotly.restyle(gd, { visible: visible, showlegend: legend });
    Plotly.relayout(gd, {
      "xaxis.tickformat": button.dataset.format,
      "xaxis.dtick": button.dataset.dtick || null
    });
    buttons.forEach(function (b) { b.classList.toggle("active", b === button); });
  }

  buttons.forEach(function (b) {
    b.addEventListener("click", function () { show(b); });
  });
})();
"""

PAGE_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Suivi du positionnement</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f6f8;
    color: #1f2937;
    margin: 0;
    padding: 32px 16px;
  }
  main { max-width: 1100px; margin: 0 auto; }
  h1 { font-size: 24px; margin: 0 0 4px; }
  .subtitle { color: #6b7280; margin: 0 0 24px; font-size: 14px; }
  section {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
  }
  h2 { font-size: 17px; margin: 0 0 12px; }
  .note { color: #6b7280; font-size: 13px; margin: 12px 0 0; }
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #f0f1f3; }
  th { font-weight: 600; color: #4b5563; white-space: nowrap; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .up { color: #15803d; font-weight: 600; }
  .down { color: #b91c1c; font-weight: 600; }
  .low { color: #9ca3af; font-style: italic; }
  .muted { color: #9ca3af; }
  .warn { color: #b45309; font-weight: 600; cursor: help; }
  .gran { display: inline-flex; gap: 2px; padding: 3px; background: #f0f1f3; border-radius: 8px; margin: 0 0 8px; }
  .gran button {
    border: 0; background: transparent; padding: 5px 14px; border-radius: 6px;
    font: inherit; font-size: 13px; color: #4b5563; cursor: pointer;
  }
  .gran button.active { background: #ffffff; color: #1f2937; font-weight: 600; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12); }
  a { color: #2563eb; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<main>
  <h1>Suivi du positionnement</h1>
  <p class="subtitle">$period. Rapport généré le $generated.</p>

  <section>
    <h2>Situation actuelle</h2>
    <div class="table-wrap">$table</div>
    <p class="note">
      Position et page : celles de la page la mieux classée. Impressions et clics : toutes pages confondues.
      Évolution : places gagnées (+) ou perdues (-) par rapport à la dernière position connue
      d'au moins $trend_days jours plus tôt. Position en gris : moins de $low_impressions impressions
      ce jour-là, donc peu fiable.
      Nb pages : nombre de pages du site positionnées sur le mot clé au dernier relevé. Le chiffre passe en orange
      dès que plusieurs pages se partagent le mot clé (risque de cannibalisation) : survole-le pour voir le détail.
    </p>
  </section>

  <section>
    <h2>Position par mot clé</h2>
    $granularity_controls
    $positions
    <script>$granularity_script</script>
    <p class="note">
      Plus la courbe est haute, mieux le site est classé. La zone verte correspond à la page 1.
      Si plusieurs pages sont positionnées sur un mot clé, la courbe suit la mieux classée.
      En vue Semaine ou Mois, la position est une moyenne pondérée par les impressions : un jour à 80
      impressions pèse plus qu'un jour à 2. Un point pâle correspond à moins de $low_impressions impressions
      sur la période, donc à une position peu fiable.
      Un trou dans une courbe signifie qu'aucune impression n'a été enregistrée sur la période.
      Clique sur un mot clé dans la légende pour l'afficher ou le masquer.
    </p>
  </section>

  <section>
    <h2>Impressions et clics</h2>
    $traffic
    <p class="note">Total sur l'ensemble des mots clés suivis et de leurs pages.</p>
  </section>
</main>
</body>
</html>
""")


def _rank(row):
    # Position la plus basse d'abord ; les lignes sans position passent en dernier
    position = row["position"] if row["position"] is not None else float("inf")
    return (position, -row["impressions"])


def load_rows(csv_file):
    """Lit le CSV : une ligne par (date, mot clé, page)."""
    rows = []
    with Path(csv_file).open(encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            rows.append({
                "date": raw["date"],
                "keyword": raw["keyword"],
                "page": raw["page"],
                "position": float(raw["position"]) if raw["position"] else None,
                "clicks": int(raw["clicks"] or 0),
                "impressions": int(raw["impressions"] or 0),
            })
    return sorted(rows, key=lambda r: (r["date"], r["keyword"], _rank(r)))


def best_per_day(rows):
    """Une ligne par (date, mot clé) : la page la mieux classée."""
    best = {}
    for row in rows:
        key = (row["date"], row["keyword"])
        if key not in best or _rank(row) < _rank(best[key]):
            best[key] = row
    return sorted(best.values(), key=lambda r: (r["date"], r["keyword"]))


def group_by_keyword(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["keyword"]].append(row)
    return dict(sorted(groups.items()))


def _style(fig, height):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=60, r=30, t=20, b=50),
        font=dict(family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"),
        hovermode="closest",
        xaxis=dict(tickformat="%d/%m"),
    )


def _period_start(day, granularity):
    if granularity == "week":
        return day - timedelta(days=day.weekday())
    if granularity == "month":
        return day.replace(day=1)
    return day


def _next_period(start, granularity):
    if granularity == "week":
        return start + timedelta(days=7)
    if granularity == "month":
        return (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start + timedelta(days=1)


def _period_label(start, granularity):
    if granularity == "week":
        return f"Semaine du {start:%d/%m/%Y}"
    if granularity == "month":
        return f"{start:%m/%Y}"
    return f"{start:%d/%m/%Y}"


def _periods(first, last, granularity):
    """Toutes les périodes entre deux dates, pour que les trous restent visibles."""
    periods = []
    current = _period_start(first, granularity)
    while current <= last:
        periods.append(current)
        current = _next_period(current, granularity)
    return periods


def aggregate_positions(rows, granularity, first, last):
    """Position par période : moyenne des positions quotidiennes (page la mieux
    classée chaque jour), pondérée par les impressions de chaque jour."""
    buckets = defaultdict(list)
    for row in best_per_day(rows):
        if row["position"] is not None:
            start = _period_start(date.fromisoformat(row["date"]), granularity)
            buckets[start].append(row)

    points = []
    for start in _periods(first, last, granularity):
        items = buckets.get(start)
        if not items:
            points.append({"start": start, "position": None, "impressions": 0, "days": 0, "page": ""})
            continue
        impressions = sum(r["impressions"] for r in items)
        if impressions:
            position = sum(r["position"] * r["impressions"] for r in items) / impressions
        else:
            position = sum(r["position"] for r in items) / len(items)
        points.append({
            "start": start,
            "position": position,
            "impressions": impressions,
            "days": len(items),
            "page": items[0]["page"],
        })
    return points


def _detail(point, granularity):
    if granularity == "day":
        return point["page"]
    days = point["days"]
    return f"{days} jour avec données" if days == 1 else f"{days} jours avec données"


def positions_figure(groups, default_granularity, first, last):
    fig = go.Figure()
    fig.add_hrect(
        y0=1,
        y1=PAGE_ONE_LAST,
        fillcolor="#22c55e",
        opacity=0.08,
        line_width=0,
        annotation_text="Page 1",
        annotation_position="bottom left",
        annotation_font_color="#15803d",
    )
    color_index = 0
    for keyword, rows in groups.items():
        if all(r["position"] is None for r in rows):
            continue
        # Même couleur pour un mot clé quelle que soit la granularité
        color = COLORS[color_index % len(COLORS)]
        color_index += 1
        for granularity, _label, _format, _dtick in GRANULARITIES:
            points = aggregate_positions(rows, granularity, first, last)
            active = granularity == default_granularity
            fig.add_trace(go.Scatter(
                x=[p["start"].isoformat() for p in points],
                y=[p["position"] for p in points],
                customdata=[
                    [
                        p["impressions"],
                        _detail(p, granularity),
                        _period_label(p["start"], granularity),
                        " (peu fiable)" if p["impressions"] < LOW_IMPRESSIONS else "",
                    ]
                    for p in points
                ],
                name=keyword,
                meta=granularity,
                visible=active,
                showlegend=active,
                mode="lines+markers",
                line=dict(color=color),
                marker=dict(
                    color=color,
                    opacity=[1 if p["impressions"] >= LOW_IMPRESSIONS else 0.35 for p in points],
                ),
                hovertemplate=(
                    "%{customdata[2]}<br>Position %{y:.1f}"
                    "<br>%{customdata[0]} impressions%{customdata[3]}"
                    "<br>%{customdata[1]}<extra>%{fullData.name}</extra>"
                ),
            ))
    _style(fig, 480)
    fig.update_layout(
        yaxis=dict(title="Position", autorange="reversed"),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def controls_html(default_granularity):
    parts = []
    for key, label, tick_format, dtick in GRANULARITIES:
        css = ' class="active"' if key == default_granularity else ""
        tick = f' data-dtick="{dtick}"' if dtick else ""
        parts.append(
            f'<button type="button" data-gran="{key}" data-format="{tick_format}"{tick}{css}>{label}</button>'
        )
    return '<div class="gran" role="group" aria-label="Granularité">' + "".join(parts) + "</div>"


def traffic_figure(rows):
    impressions = defaultdict(int)
    clicks = defaultdict(int)
    for row in rows:
        impressions[row["date"]] += row["impressions"]
        clicks[row["date"]] += row["clicks"]
    dates = sorted(impressions)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates,
        y=[impressions[d] for d in dates],
        name="Impressions",
        marker_color="#a5bde8",
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=[clicks[d] for d in dates],
        name="Clics",
        mode="lines+markers",
        marker_color="#e8743b",
        yaxis="y2",
    ))
    _style(fig, 380)
    clicks_axis = dict(
        title="Clics", overlaying="y", side="right", showgrid=False, rangemode="tozero"
    )
    if max(clicks.values()) <= 10:
        # Peu de clics : on force des graduations entières (0, 1, 2...)
        clicks_axis["dtick"] = 1
    fig.update_layout(
        yaxis=dict(title="Impressions", rangemode="tozero"),
        yaxis2=clicks_axis,
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def summarize(groups):
    summary = []
    for keyword, rows in groups.items():
        # Position et page : la mieux classée chaque jour. Clics et impressions
        # ci-dessous : additionnés sur toutes les pages
        seen = [r for r in best_per_day(rows) if r["position"] is not None]
        latest = seen[-1] if seen else None
        change = None
        if latest:
            limit = date.fromisoformat(latest["date"]) - timedelta(days=TREND_DAYS)
            older = [r for r in seen if r["date"] <= limit.isoformat()]
            if older:
                change = older[-1]["position"] - latest["position"]
        summary.append({
            "keyword": keyword,
            "latest": latest,
            # Pages positionnées au dernier relevé, la mieux classée d'abord
            "pages": sorted(
                (
                    r for r in rows
                    if latest and r["date"] == latest["date"] and r["position"] is not None
                ),
                key=_rank,
            ),
            "change": change,
            "impressions": sum(r["impressions"] for r in rows),
            "clicks": sum(r["clicks"] for r in rows),
        })
    summary.sort(key=lambda s: (
        s["latest"] is None,
        s["latest"]["position"] if s["latest"] else 0,
        s["keyword"],
    ))
    return summary


def _number(value):
    return f"{value:,}".replace(",", " ")


def table_html(summary):
    lines = [
        "<table>",
        "<thead><tr>"
        "<th>Mot clé</th>"
        '<th class="num">Position</th>'
        '<th class="num">Évolution</th>'
        '<th class="num">Impressions</th>'
        '<th class="num">Clics</th>'
        '<th class="num">Nb pages</th>'
        "<th>Page</th>"
        "<th>Dernier relevé</th>"
        "</tr></thead>",
        "<tbody>",
    ]
    for item in summary:
        latest = item["latest"]
        if latest is None:
            position = '<td class="num muted">-</td>'
            page = '<td class="muted">-</td>'
            seen_on = '<td class="muted">-</td>'
            pages_cell = '<td class="num muted">-</td>'
        else:
            low = latest["impressions"] < LOW_IMPRESSIONS
            css = "num low" if low else "num"
            tip = (
                f' title="Moins de {LOW_IMPRESSIONS} impressions ce jour-là : position peu fiable"'
                if low
                else ""
            )
            position = f'<td class="{css}"{tip}>{latest["position"]:.1f}</td>'
            url = latest["page"]
            label = urlparse(url).path or "/"
            page = f'<td><a href="{escape(url)}" target="_blank" rel="noopener">{escape(label)}</a></td>'
            seen_on = f'<td>{date.fromisoformat(latest["date"]).strftime("%d/%m/%Y")}</td>'
            pages = item["pages"]
            if len(pages) > 1:
                detail = "&#10;".join(
                    escape(
                        f'{urlparse(p["page"]).path or "/"} : position {p["position"]:.1f}, '
                        f'{p["impressions"]} impressions'
                    )
                    for p in pages
                )
                pages_cell = f'<td class="num warn" title="{detail}">{len(pages)}</td>'
            else:
                pages_cell = f'<td class="num">{len(pages)}</td>'

        change = item["change"]
        if change is None:
            change_cell = '<td class="num muted">n/d</td>'
        elif abs(change) < 0.05:
            change_cell = '<td class="num">stable</td>'
        else:
            css = "up" if change > 0 else "down"
            change_cell = f'<td class="num {css}">{change:+.1f}</td>'

        lines.append(
            "<tr>"
            f"<td>{escape(item['keyword'])}</td>"
            f"{position}{change_cell}"
            f'<td class="num">{_number(item["impressions"])}</td>'
            f'<td class="num">{_number(item["clicks"])}</td>'
            f"{pages_cell}{page}{seen_on}"
            "</tr>"
        )
    lines += ["</tbody>", "</table>"]
    return "\n".join(lines)


def generate_report(csv_file, output_file):
    """Génère le rapport HTML. Renvoie True si le fichier a été écrit."""
    csv_file = Path(csv_file)
    if not csv_file.exists():
        print(f"Aucune donnée : {csv_file} n'existe pas encore. Lance d'abord un relevé.")
        return False

    rows = load_rows(csv_file)
    if not rows:
        print("Le fichier CSV ne contient aucune donnée.")
        return False

    groups = group_by_keyword(rows)
    first_day = date.fromisoformat(rows[0]["date"]).strftime("%d/%m/%Y")
    last_day = date.fromisoformat(rows[-1]["date"]).strftime("%d/%m/%Y")
    days = len({r["date"] for r in rows})
    period = f"Données du {first_day} au {last_day} ({days} jours relevés, {len(groups)} mots clés suivis)"

    plotly_config = {"displaylogo": False}
    # La bibliothèque Plotly est embarquée une seule fois (dans le premier graphique)
    # pour que le fichier fonctionne sans connexion
    default_granularity = "week" if days >= WEEK_DEFAULT_MIN_DAYS else "day"
    positions = positions_figure(
        groups,
        default_granularity,
        date.fromisoformat(rows[0]["date"]),
        date.fromisoformat(rows[-1]["date"]),
    ).to_html(
        full_html=False,
        include_plotlyjs=True,
        config=plotly_config,
        div_id="positions-chart",
    )
    traffic = traffic_figure(rows).to_html(
        full_html=False, include_plotlyjs=False, config=plotly_config
    )

    html = PAGE_TEMPLATE.substitute(
        period=period,
        generated=datetime.now().strftime("%d/%m/%Y à %H:%M"),
        table=table_html(summarize(groups)),
        granularity_controls=controls_html(default_granularity),
        granularity_script=GRANULARITY_SCRIPT,
        positions=positions,
        traffic=traffic,
        trend_days=TREND_DAYS,
        low_impressions=LOW_IMPRESSIONS,
    )

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html, encoding="utf-8")
    print(f"Rapport généré : {output_file}")
    return True
