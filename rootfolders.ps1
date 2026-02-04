# Root folders
$folders = @(
    "app",
    "app/pages",

    "core",
    "core/model",
    "core/solver",
    "core/optimization",
    "core/graph",

    "visualization",

    "data",
    "data/examples",
    "data/saved_models",

    "tests",

    "docs",
    "docs/uml",
    "docs/figures"
)

foreach ($folder in $folders) {
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
}

# Files
$files = @(
    "app/main.py",
    "app/ui_utils.py",
    "app/pages/01_modell_definition.py",
    "app/pages/02_optimierung.py",
    "app/pages/03_visualisierung.py",

    "core/model/node.py",
    "core/model/spring.py",
    "core/model/structure.py",
    "core/model/boundary_conditions.py",

    "core/solver/stiffness_matrix.py",
    "core/solver/solver.py",
    "core/solver/regularization.py",

    "core/optimization/optimizer_base.py",
    "core/optimization/energy_based_optimizer.py",
    "core/optimization/connectivity_check.py",

    "core/graph/graph_builder.py",
    "core/graph/incidence_matrix.py",

    "visualization/plot_structure.py",
    "visualization/plot_deformation.py",
    "visualization/plot_energy_heatmap.py",
    "visualization/export_image.py",

    "data/examples/mbb_beam.json",

    "tests/test_solver.py",
    "tests/test_stiffness_matrix.py",
    "tests/test_connectivity.py",

    "README.md",
    "requirements.txt",
    ".gitignore"
)

foreach ($file in $files) {
    if (-not (Test-Path $file)) {
        New-Item -ItemType File -Path $file | Out-Null
    }
}
