import plotly.graph_objects as go


def plot_heatmap(structure, energies=None) -> go.Figure:
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

    # Knoten
    nx_vals, ny_vals, colors, symbols, hover = [], [], [], [], []
    for n in structure.nodes:
        if not n.active:
            continue
        nx_vals.append(n.x)
        ny_vals.append(n.y)
        if n.fix_x or n.fix_y:
            colors.append("#FF6B35")
            symbols.append("triangle-up")
            hover.append(f"Knoten {n.id}<br>Auflager: fix_x={n.fix_x}, fix_y={n.fix_y}")
        elif abs(n.fx) > 0 or abs(n.fy) > 0:
            colors.append("#FFD700")
            symbols.append("diamond")
            hover.append(f"Knoten {n.id}<br>Last: Fy={n.fy:.2f}")
        else:
            colors.append("#888888")
            symbols.append("circle")
            hover.append(f"Knoten {n.id}")

    fig.add_trace(go.Scatter(
        x=nx_vals, y=ny_vals,
        mode="markers",
        marker=dict(color=colors, size=8, symbol=symbols,
                    line=dict(width=0.5, color="#222")),
        text=hover,
        hoverinfo="text",
        showlegend=False,
    ))

    fig.update_layout(
        paper_bgcolor="#1A1A2E",
        plot_bgcolor="#16213E",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=400,
    )
    return fig