"""
Speaker Network Graph — Who's connected to what on AIM's channel.

Business framing for AIM:
  "Your most influential guests and brand associations."
  "Which speaker should you re-invite? Who's connected to rising topics?"

Pyvis interactive HTML graph:
  - Nodes: people (red), orgs (blue), tech tools (green)
  - Edges: co-occurrence within the same transcript
  - Node size: total mentions across all videos
  - Edge weight: co-occurrence frequency

Judges can click, zoom, drag — fully interactive.
"""

import json
from collections import Counter, defaultdict

from pyvis.network import Network

from pipeline.database import get_connection

# Node types and colors
NODE_COLORS = {
    "person": "#e74c3c",   # red
    "org":    "#3498db",   # blue
    "tech":   "#2ecc71",   # green
}


def build_network(min_mentions: int = 3,
                  max_nodes: int = 100,
                  output_path: str = "data/speaker_network.html") -> None:
    """Build the interactive speaker network graph."""
    con = get_connection()

    rows = con.execute("""
        SELECT entities_person, entities_org, entities_tech, year
        FROM episodic
        WHERE status IN ('ANALYZED', 'SUMMARIZED', 'AUDITED')
          AND (entities_person IS NOT NULL
               OR entities_org IS NOT NULL
               OR entities_tech IS NOT NULL)
    """).fetchall()
    con.close()

    # Count total mentions per entity
    person_counts = Counter()
    org_counts = Counter()
    tech_counts = Counter()

    # Co-occurrence: (entity_a, entity_b) → count
    co_occurrence = Counter()

    for persons_j, orgs_j, tech_j, year in rows:
        persons = json.loads(persons_j) if persons_j else []
        orgs = json.loads(orgs_j) if orgs_j else []
        tech = json.loads(tech_j) if tech_j else []

        # Cap to top 5 per video to avoid noise
        persons = persons[:5]
        orgs = orgs[:5]
        tech = tech[:5]

        for p in persons:
            person_counts[p] += 1
        for o in orgs:
            org_counts[o] += 1
        for t in tech:
            tech_counts[t] += 1

        # Co-occurrence: persons ↔ orgs, persons ↔ tech
        all_entities = (
            [("person", p) for p in persons] +
            [("org", o) for o in orgs] +
            [("tech", t) for t in tech]
        )
        for i in range(len(all_entities)):
            for j in range(i + 1, len(all_entities)):
                key = tuple(sorted([all_entities[i][1], all_entities[j][1]]))
                co_occurrence[key] += 1

    # Filter by min_mentions
    top_persons = {k: v for k, v in person_counts.items() if v >= min_mentions}
    top_orgs    = {k: v for k, v in org_counts.items() if v >= min_mentions}
    top_tech    = {k: v for k, v in tech_counts.items() if v >= min_mentions}

    # Limit total nodes
    def top_n(d, n):
        return dict(sorted(d.items(), key=lambda x: -x[1])[:n])

    n_each = max_nodes // 3
    top_persons = top_n(top_persons, n_each)
    top_orgs    = top_n(top_orgs, n_each)
    top_tech    = top_n(top_tech, n_each)

    all_nodes = (
        [(k, "person", v) for k, v in top_persons.items()] +
        [(k, "org", v) for k, v in top_orgs.items()] +
        [(k, "tech", v) for k, v in top_tech.items()]
    )
    node_names = {n[0] for n in all_nodes}

    # Build Pyvis network
    net = Network(
        height="750px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="white",
        notebook=False,
    )
    net.set_options("""
    var options = {
      "nodes": {
        "borderWidth": 2,
        "font": {"size": 14, "face": "Arial"}
      },
      "edges": {
        "color": {"opacity": 0.4},
        "smooth": {"type": "dynamic"}
      },
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -80,
          "centralGravity": 0.01,
          "springLength": 100,
          "springConstant": 0.05
        },
        "solver": "forceAtlas2Based",
        "stabilization": {"iterations": 150}
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 200
      }
    }
    """)

    # Add nodes
    max_mentions = max(v for _, _, v in all_nodes) if all_nodes else 1
    for name, ntype, count in all_nodes:
        size = 10 + (count / max_mentions) * 40  # scale 10-50
        net.add_node(
            name,
            label=name,
            color=NODE_COLORS[ntype],
            size=size,
            title=f"{name}<br>Type: {ntype}<br>Mentions: {count}",
            group=ntype,
        )

    # Add edges (only between nodes we've included)
    for (a, b), weight in co_occurrence.items():
        if a in node_names and b in node_names and weight >= 2:
            net.add_edge(a, b, value=weight,
                         title=f"Co-occurs {weight}x")

    net.save_graph(output_path)
    print(f"Speaker Network saved to {output_path}")
    print(f"  Nodes: {len(all_nodes)} (persons={len(top_persons)}, "
          f"orgs={len(top_orgs)}, tech={len(top_tech)})")
    print(f"  Edges: co-occurrence graph built")


if __name__ == "__main__":
    build_network()
