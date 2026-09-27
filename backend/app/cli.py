import logging
import os

import click
from flask import Flask

from .extensions import db
from .models import Device, Plot, User
from .services.auth import ROLES, create_user
from .services.demo import clear_demo, seed_demo
from .services.device_sim import run_simulated_devices, simulate_device
from .services.fertiliser import seed_fertiliser
from .services.iot import create_device
from .services.mqtt_bridge import run_bridge
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
        for username, role in (("farmer", "farmer"), ("expert", "expert")):
            password = os.getenv(f"DEMO_{role.upper()}_PASSWORD")
            if password:
                create_user(username, password, role)
                click.echo(f"demo user '{username}' ({role}) ready")
        farmer = User.query.filter_by(username="farmer", role="farmer").one_or_none()
        if Plot.query.filter_by(is_simulated=False).count() == 0:
            for name, crop, lat, lon in DEFAULT_PLOTS:
                create_plot(name, crop, lat, lon, area_m2=400, num_plants=200, owner=farmer)
        click.echo("seeded disease profiles, fertiliser tables and plots")

    @app.cli.command("create-user")
    @click.argument("username")
    @click.option("--role", type=click.Choice(ROLES), default="farmer")
    @click.password_option()
    def create_user_cmd(username, role, password):
        """Create or reset a login (farmer or expert)."""
        try:
            create_user(username, password, role)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"user '{username}' ({role}) saved")

    @app.cli.command("assign-plots")
    @click.argument("username")
    @click.option("--plot", "plot_ids", type=int, multiple=True, help="Plot id (repeatable). Default: every unowned real plot.")
    def assign_plots_cmd(username, plot_ids):
        """Give a farmer ownership of plots so they see them in Scan, Fertiliser and Farm monitor."""
        user = User.query.filter_by(username=username).one_or_none()
        if user is None:
            raise click.ClickException(f"no user '{username}'")
        q = Plot.query.filter(Plot.id.in_(plot_ids)) if plot_ids else Plot.query.filter_by(owner_id=None, is_simulated=False)
        plots = q.all()
        for plot in plots:
            plot.owner_id = user.id
        db.session.commit()
        click.echo(f"{len(plots)} plot(s) now owned by {username}")

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

    @app.cli.command("sim-devices")
    @click.option("--add", is_flag=True, help="First attach a Simulated device to every real plot that has no device.")
    @click.option("--hours", type=int, default=None, help="Backfill window for devices with no history.")
    def sim_devices_cmd(add, hours):
        """Advance all Simulated devices up to now (readings labelled "Simulated device")."""
        if add:
            for plot in Plot.query.filter_by(is_simulated=False).order_by(Plot.id):
                if not Device.query.filter_by(plot_id=plot.id).first():
                    device, _ = create_device(plot, simulated=True)
                    click.echo(f"added {device.uid} to {plot.name}")
        if hours:
            for device in Device.query.filter_by(is_simulated=True, kind="sensor"):
                click.echo(f"{device.uid}: +{simulate_device(device, backfill_hours=hours)} readings")
        else:
            for uid, n in run_simulated_devices().items():
                click.echo(f"{uid}: +{n} readings")

    @app.cli.command("mqtt-bridge")
    def mqtt_bridge_cmd():
        """Store IoTDA-style MQTT property reports from MQTT_BROKER_URL (local Mosquitto)."""
        if not app.config["MQTT_BROKER_URL"]:
            raise click.ClickException("set MQTT_BROKER_URL, e.g. mqtt://localhost:1883")
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        run_bridge(app)

    @app.cli.command("add-device")
    @click.argument("plot_id", type=int)
    @click.option("--name", default=None)
    @click.option("--simulated", is_flag=True, help="For scripts/device_simulator.py: labelled \"Simulated device\".")
    def add_device_cmd(plot_id, name, simulated):
        """Register a sensor on a plot and print its one-time key."""
        plot = db.session.get(Plot, plot_id)
        if plot is None:
            raise click.ClickException("plot not found")
        device, key = create_device(plot, name, simulated=simulated, external=simulated)
        click.echo(f"device id:  {device.uid}\ndevice key: {key}\n(store the key now; it is not shown again)")
