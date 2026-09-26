import click
from flask import Flask

from .models import Plot
from .services.demo import clear_demo, seed_demo
from .services.fertiliser import seed_fertiliser
from .services.profiles import seed_profiles
from .services.risk_engine import refresh_all
from .services.scans import create_plot

DEFAULT_PLOTS = [
    ("Plot A", "chilli", 1.8548, 103.3345),
    ("Plot B", "chilli", 1.8580, 103.3390),
    ("Plot C", "tomato", 1.8520, 103.3300),
]


def register_cli(app: Flask):
    @app.cli.command("seed-base")
    def seed_base():
        """Seed disease profiles, fertiliser tables and example plots (idempotent)."""
        seed_profiles()
        seed_fertiliser()
        if Plot.query.filter_by(is_simulated=False).count() == 0:
            for name, crop, lat, lon in DEFAULT_PLOTS:
                create_plot(name, crop, lat, lon, area_m2=400, num_plants=200)
        click.echo("seeded disease profiles, fertiliser tables and plots")

    @app.cli.command("seed-demo")
    @click.option("--clear", is_flag=True, help="Remove the simulated scenario instead of creating it.")
    def seed_demo_cmd(clear):
        """Create (or --clear) the Simulated scenario demo scans."""
        if clear:
            click.echo(f"removed {clear_demo()} simulated scans")
        else:
            click.echo(f"created {seed_demo()} simulated scans (Simulated scenario)")

    @app.cli.command("refresh-risk")
    def refresh_risk_cmd():
        """Fetch weather for active cells and recompute all risk layers now."""
        click.echo(refresh_all())
