import click
from flask import Flask

from .models import Plot
from .services.profiles import seed_profiles
from .services.scans import create_plot

DEFAULT_PLOTS = [
    ("Plot A", "chilli", 1.8548, 103.3345),
    ("Plot B", "chilli", 1.8580, 103.3390),
    ("Plot C", "tomato", 1.8520, 103.3300),
]


def register_cli(app: Flask):
    @app.cli.command("seed-base")
    def seed_base():
        """Seed disease profiles and example plots (idempotent)."""
        seed_profiles()
        if Plot.query.filter_by(is_simulated=False).count() == 0:
            for name, crop, lat, lon in DEFAULT_PLOTS:
                create_plot(name, crop, lat, lon, area_m2=400, num_plants=200)
        click.echo("seeded disease profiles and plots")
