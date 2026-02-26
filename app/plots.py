import io

import numpy as np
import plotly.graph_objects as go
from PIL import Image

from core.model import structure
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


def plot_deformed_structure(structure, u, scale, u_ref: float = None) -> go.Figure:
    fig = go.Figure()

    # Ausreißer clippen: max. 3x die Referenzverschiebung erlaubt
    clip = 3.0 * u_ref if u_ref is not None and u_ref > 0 else None

    # --- Unverformte Struktur (grau, dünn) als Referenz ---
    sx_orig, sy_orig = [], []
    for s in structure.springs:
        if not s.active:
            continue
        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        if not ni.active or not nj.active:
            continue
        sx_orig += [ni.x, nj.x, None]
        sy_orig += [ni.y, nj.y, None]

    fig.add_trace(go.Scatter(
        x=sx_orig, y=sy_orig,
        mode="lines",
        line=dict(color="rgba(100,120,160,0.35)", width=1.0),
        hoverinfo="skip",
        showlegend=True,
        name="Unverformt",
    ))

    # --- Verformte Struktur (rot) ---
    sx_def, sy_def = [], []
    for s in structure.springs:
        if not s.active:
            continue
        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        if not ni.active or not nj.active:
            continue

        ux_i = float(u[2 * ni.id])
        uy_i = float(u[2 * ni.id + 1])
        ux_j = float(u[2 * nj.id])
        uy_j = float(u[2 * nj.id + 1])

        if clip is not None:
            ux_i = float(np.clip(ux_i, -clip, clip))
            uy_i = float(np.clip(uy_i, -clip, clip))
            ux_j = float(np.clip(ux_j, -clip, clip))
            uy_j = float(np.clip(uy_j, -clip, clip))

        sx_def += [ni.x + scale * ux_i, nj.x + scale * ux_j, None]
        sy_def += [ni.y + scale * uy_i, nj.y + scale * uy_j, None]

    fig.add_trace(go.Scatter(
        x=sx_def, y=sy_def,
        mode="lines",
        line=dict(color="#FF4444", width=2),
        hoverinfo="skip",
        showlegend=True,
        name="Verformt",
    ))

    fig.update_layout(
        paper_bgcolor="#1A1A2E",
        plot_bgcolor="#16213E",
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            font=dict(color="white"),
            bgcolor="rgba(0,0,0,0)",
            orientation="h",
            x=0.01, y=0.99,
        ),
        xaxis=dict(
            showgrid=False, zeroline=False, showticklabels=False,
            scaleanchor="y", scaleratio=1,
        ),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=450,
    )

    return fig


def plot_replay_structure(structure, removed_so_far: set, just_removed: set) -> go.Figure:
    fig = go.Figure()
    all_removed = removed_so_far | just_removed

    # --- Bereits entfernte Federn (sehr blass) ---
    sx_gone, sy_gone = [], []
    for s in structure.springs:
        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        if ni.id in removed_so_far or nj.id in removed_so_far:
            sx_gone += [ni.x, nj.x, None]
            sy_gone += [ni.y, nj.y, None]

    fig.add_trace(go.Scatter(
        x=sx_gone, y=sy_gone,
        mode="lines",
        line=dict(color="rgba(80,80,100,0.15)", width=0.8),
        hoverinfo="skip", showlegend=False,
    ))

    # --- Aktive Federn ---
    sx_act, sy_act = [], []
    for s in structure.springs:
        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        if ni.id not in all_removed and nj.id not in all_removed:
            sx_act += [ni.x, nj.x, None]
            sy_act += [ni.y, nj.y, None]

    fig.add_trace(go.Scatter(
        x=sx_act, y=sy_act,
        mode="lines",
        line=dict(color="#4A90D9", width=1.5),
        hoverinfo="skip", showlegend=False,
    ))

    # --- Gerade entfernte Federn (orange) ---
    sx_rem, sy_rem = [], []
    for s in structure.springs:
        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        if ni.id not in removed_so_far and nj.id not in removed_so_far:
            if ni.id in just_removed or nj.id in just_removed:
                sx_rem += [ni.x, nj.x, None]
                sy_rem += [ni.y, nj.y, None]

    fig.add_trace(go.Scatter(
        x=sx_rem, y=sy_rem,
        mode="lines",
        line=dict(color="#FF8C00", width=2),
        hoverinfo="skip", showlegend=False,
    ))

    # --- Gerade entfernte Knoten (orange X) ---
    rem_nodes = [structure.nodes[nid] for nid in just_removed]
    if rem_nodes:
        fig.add_trace(go.Scatter(
            x=[n.x for n in rem_nodes],
            y=[n.y for n in rem_nodes],
            mode="markers",
            marker=dict(color="#FF8C00", size=9, symbol="x", line=dict(width=2, color="#FF8C00")),
            hovertext=[f"Knoten {n.id}" for n in rem_nodes],
            hoverinfo="text", showlegend=False,
        ))

    fig.update_layout(
        paper_bgcolor="#1A1A2E",
        plot_bgcolor="#16213E",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=450,
    )
    return fig


def generate_mode_animation_gif(
    structure,
    eigvec: np.ndarray,
    scale: float,
    u_ref: float,
    n_frames: int = 24,
    fps: int = 12,
    width: int = 800,
    height: int = 450,
    on_progress=None,
) -> bytes:
    """Erzeugt ein GIF der Struktur, die im ersten Eigenmode schwingt."""
    active = [n for n in structure.nodes if n.active]
    all_x = [n.x for n in active]
    all_y = [n.y for n in active]

    # Feste Achsengrenzen: Strukturgröße + maximale Auslenkung als Puffer
    bbox = max(max(all_x) - min(all_x), max(all_y) - min(all_y), 1.0)
    margin = bbox * 0.08 + u_ref * scale * 1.5
    x_range = [min(all_x) - margin, max(all_x) + margin]
    y_range = [min(all_y) - margin, max(all_y) + margin]

    layout_update = dict(
        xaxis=dict(range=x_range, showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(range=y_range, showgrid=False, zeroline=False, showticklabels=False),
    )

    frames: list[Image.Image] = []
    for k in range(n_frames):
        amplitude = np.cos(2.0 * np.pi * k / n_frames)
        u_frame = eigvec * amplitude
        fig = plot_deformed_structure(structure, u_frame, scale, u_ref=u_ref)
        fig.update_layout(**layout_update)
        frames.append(
            Image.open(io.BytesIO(fig.to_image(format="png", width=width, height=height)))
            .convert("RGB")
            .quantize(colors=256)
        )
        if on_progress:
            on_progress((k + 1) / n_frames)

    gif_buf = io.BytesIO()
    frames[0].save(
        gif_buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=1000 // fps,
        loop=0,
    )
    return gif_buf.getvalue()


def generate_replay_gif(
    structure,
    hist,
    fps: int = 5,
    width: int = 800,
    height: int = 450,
    on_progress=None,
) -> bytes:
    n_steps = len(hist.removed_nodes_per_iter)
    total_frames = n_steps + 1  # +1 for initial frame

    all_x = [n.x for n in structure.nodes]
    all_y = [n.y for n in structure.nodes]
    pad_x = (max(all_x) - min(all_x)) * 0.08
    pad_y = (max(all_y) - min(all_y)) * 0.08
    x_range = [min(all_x) - pad_x, max(all_x) + pad_x]
    y_range = [min(all_y) - pad_y, max(all_y) + pad_y]

    layout_update = dict(
        xaxis=dict(range=x_range, showgrid=False, zeroline=False, showticklabels=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(range=y_range, showgrid=False, zeroline=False, showticklabels=False),
    )

    frames: list[Image.Image] = []
    removed_so_far: set = set()

    fig = plot_replay_structure(structure, set(), set())
    fig.update_layout(**layout_update)
    frames.append(Image.open(io.BytesIO(fig.to_image(format="png", width=width, height=height))).convert("RGB").quantize(colors=256))
    if on_progress:
        on_progress(1 / total_frames)

    for s in range(n_steps):
        just_removed = set(hist.removed_nodes_per_iter[s])
        fig = plot_replay_structure(structure, removed_so_far, just_removed)
        fig.update_layout(**layout_update)
        frames.append(Image.open(io.BytesIO(fig.to_image(format="png", width=width, height=height))).convert("RGB").quantize(colors=256))
        removed_so_far = removed_so_far | just_removed
        if on_progress:
            on_progress((s + 2) / total_frames)

    # Letzten Frame 3 Sekunden einfrieren
    frames.extend([frames[-1]] * max(1, fps * 3))

    gif_buf = io.BytesIO()
    frames[0].save(
        gif_buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=1000 // fps,
        loop=0,
    )
    return gif_buf.getvalue()


def plot_load_paths_with_arrows(structure, u, energies, arrow_scale=1.0, top_n=80):
    """
    Lastpfade als Pfeile entlang der Stäbe.
    Pfeillänge ~ energies[i] (gleiches Mapping wie Heatmap: Feder i -> energies[i]).
    Richtung entlang Stab; Zug/Druck-Vorzeichen wird aus u über dL bestimmt.
    """

    segs = []

    for i, s in enumerate(structure.springs):
        if not getattr(s, "active", True):
            continue

        n1 = structure.nodes[s.node_i]
        n2 = structure.nodes[s.node_j]
        if not n1.active or not n2.active:
            continue

        x1, y1 = n1.x, n1.y
        x2, y2 = n2.x, n2.y

        r0 = np.array([x2 - x1, y2 - y1], dtype=float)
        L0 = np.linalg.norm(r0)
        if L0 == 0:
            continue
        e = r0 / L0

        # (Vorzeichen)
        u1 = np.array([u[2*n1.id], u[2*n1.id + 1]], dtype=float)
        u2 = np.array([u[2*n2.id], u[2*n2.id + 1]], dtype=float)
        dL = float(np.dot((u2 - u1), e))
        sign = 1.0 if dL >= 0 else -1.0

        # energies[i]
        mag = float(abs(energies[i]))
        F = sign * mag

        segs.append((x1, y1, x2, y2, F, mag))

    if len(segs) == 0:
        fig = go.Figure()
        fig.update_layout(title="Keine aktiven Stäbe / Lastpfade nicht berechenbar")
        return fig

    mags = np.array([m for *_, m in segs], dtype=float)

    order = np.argsort(mags)[::-1]  # stärkste zuerst
    if top_n is not None:
        order = order[: min(top_n, len(order))]

    Fmax = float(np.max(mags)) if np.max(mags) > 0 else 1.0

    fig = go.Figure()
    x_all, y_all = [], []
    for (x1, y1, x2, y2, _, _) in segs:
        x_all += [x1, x2, None]
        y_all += [y1, y2, None]

    fig.add_trace(go.Scatter(
        x=x_all, y=y_all,
        mode="lines",
        line=dict(width=2),
        hoverinfo="skip",
        opacity=0.5
    ))

    #  Pfeile
    nodes_active = [n for n in structure.nodes if n.active]
    xs = [n.x for n in nodes_active]
    ys = [n.y for n in nodes_active]
    bbox = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    base_len = 0.08 * bbox * arrow_scale

    annotations = []

    for idx in order:
        x1, y1, x2, y2, F, mag = segs[idx]

        r0 = np.array([x2 - x1, y2 - y1], dtype=float)
        L0 = np.linalg.norm(r0)
        if L0 == 0:
            continue
        e = r0 / L0

        xm = 0.5 * (x1 + x2)
        ym = 0.5 * (y1 + y2)

        strength = mag / Fmax
        direction = 1.0 if F >= 0 else -1.0

        dx = direction * e[0] * base_len * strength
        dy = direction * e[1] * base_len * strength

        annotations.append(dict(
            x=xm + dx, y=ym + dy,
            ax=xm, ay=ym,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=1,
            arrowwidth=2,
            opacity=0.9,
        ))

    fig.update_layout(
        showlegend=False,
        annotations=annotations,
        xaxis=dict(scaleanchor="y", scaleratio=1),
    )

    return fig