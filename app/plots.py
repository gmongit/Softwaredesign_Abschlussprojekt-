import plotly.graph_objects as go

from core.model.structure import Structure


def _base_layout() -> dict:
    return dict(
        paper_bgcolor="#1A1A2E",
        plot_bgcolor="#16213E",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=400,
    )


def _node_traces(structure: Structure):
    nx_vals, ny_vals, colors, symbols, sizes, hover, node_ids = [], [], [], [], [], [], []
    for n in structure.nodes:
        if not n.active:
            continue
        nx_vals.append(n.x)
        ny_vals.append(n.y)
        node_ids.append(n.id)
        if n.fix_x and n.fix_y:
            # Festlager (Pin) — gefülltes Dreieck
            colors.append("#FF6B35")
            symbols.append("triangle-down")
            sizes.append(14)
            hover.append(f"Knoten {n.id}<br>Festlager (fix_x, fix_y)")
        elif n.fix_x or n.fix_y:
            # Loslager (Roller) — offenes Dreieck
            colors.append("#FF9F1C")
            symbols.append("triangle-down-open")
            sizes.append(14)
            hover.append(f"Knoten {n.id}<br>Loslager (fix_y)")
        elif abs(n.fx) > 0 or abs(n.fy) > 0:
            colors.append("#FFD700")
            symbols.append("arrow-down" if n.fy < 0 else "arrow-up" if n.fy > 0 else "diamond")
            sizes.append(12)
            hover.append(f"Knoten {n.id}<br>Last: Fy={n.fy:.2f}")
        else:
            colors.append("#888888")
            symbols.append("circle")
            sizes.append(6)
            hover.append(f"Knoten {n.id}")
    return nx_vals, ny_vals, colors, symbols, sizes, hover, node_ids


def _inactive_node_trace(structure: Structure):
    ix, iy, ids, hover = [], [], [], []
    for n in structure.nodes:
        if n.active:
            continue
        ix.append(n.x)
        iy.append(n.y)
        ids.append(n.id)
        hover.append(f"Knoten {n.id} (inaktiv)")
    return ix, iy, ids, hover


def plot_structure(structure: Structure, show_inactive: bool = False) -> go.Figure:
    sx, sy = [], []
    for s in structure.springs:
        if not s.active:
            continue
        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        sx += [ni.x, nj.x, None]
        sy += [ni.y, nj.y, None]

    nx_vals, ny_vals, colors, symbols, sizes, hover, node_ids = _node_traces(structure)

    fig = go.Figure()

    # Trace 0: Federn (Linien)
    fig.add_trace(go.Scatter(
        x=sx, y=sy,
        mode="lines",
        line=dict(color="#4A90D9", width=1.2),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Trace 1: Aktive Knoten (Marker)
    fig.add_trace(go.Scatter(
        x=nx_vals, y=ny_vals,
        mode="markers",
        marker=dict(color=colors, size=sizes, symbol=symbols,
                    line=dict(width=1, color="#222")),
        text=hover,
        hoverinfo="text",
        customdata=node_ids,
        showlegend=False,
    ))

    # Trace 2: Inaktive Knoten (optional, halbtransparent)
    if show_inactive:
        ix, iy, iids, ihover = _inactive_node_trace(structure)
        if ix:
            fig.add_trace(go.Scatter(
                x=ix, y=iy,
                mode="markers",
                marker=dict(color="rgba(100,100,100,0.3)", size=5, symbol="x-thin",
                            line=dict(width=0.5, color="rgba(100,100,100,0.3)")),
                text=ihover,
                hoverinfo="text",
                customdata=iids,
                showlegend=False,
            ))

    fig.update_layout(**_base_layout())
    return fig


def plot_heatmap(structure: Structure, energies=None) -> go.Figure:
    fig = go.Figure()

    e_max = max(energies) if energies is not None and max(energies) > 0 else 1.0

    for i, s in enumerate(structure.springs):
        if not s.active:
            continue
        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        if not (ni.active and nj.active):
            continue

        if energies is not None:
            t = energies[i] / e_max
            r = int(255 * min(1.0, 2 * t))
            g = int(255 * min(1.0, 2 * t) * (1 - t))
            b = int(255 * max(0.0, 1 - 2 * t))
            color = f"rgb({r},{g},{b})"
        else:
            color = "#4A90D9"

        fig.add_trace(go.Scatter(
            x=[ni.x, nj.x],
            y=[ni.y, nj.y],
            mode="lines",
            line=dict(color=color, width=1.2),
            hoverinfo="skip",
            showlegend=False,
        ))

    nx_vals, ny_vals, colors, symbols, sizes, hover, node_ids = _node_traces(structure)
    fig.add_trace(go.Scatter(
        x=nx_vals, y=ny_vals,
        mode="markers",
        marker=dict(color=colors, size=sizes, symbol=symbols,
                    line=dict(width=1, color="#222")),
        text=hover,
        hoverinfo="text",
        customdata=node_ids,
        showlegend=False,
    ))
    fig.update_layout(**_base_layout())
    return fig