from datetime import datetime, timezone

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Plot(db.Model):
    __tablename__ = "plots"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    crop = db.Column(db.String(20), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    grid_cell = db.Column(db.String(32), nullable=False, index=True)
    region = db.Column(db.String(8), nullable=False, index=True)
    area_m2 = db.Column(db.Float)
    num_plants = db.Column(db.Integer)
    is_simulated = db.Column(db.Boolean, nullable=False, default=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id, "owner_id": self.owner_id, "name": self.name, "crop": self.crop, "lat": self.lat, "lon": self.lon,
            "grid_cell": self.grid_cell, "region": self.region, "area_m2": self.area_m2,
            "num_plants": self.num_plants, "is_simulated": self.is_simulated,
        }


class Scan(db.Model):
    __tablename__ = "scans"
    id = db.Column(db.Integer, primary_key=True)
    plot_id = db.Column(db.Integer, db.ForeignKey("plots.id"), nullable=True, index=True)
    crop = db.Column(db.String(20), nullable=False, index=True)
    diagnosis = db.Column(db.String(64), nullable=False, index=True)
    confidence = db.Column(db.Float, nullable=False)
    top3 = db.Column(db.JSON, nullable=False)
    severity = db.Column(db.Float, nullable=False, default=0.0)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    grid_cell = db.Column(db.String(32), nullable=False, index=True)
    region = db.Column(db.String(8), nullable=False, index=True)
    image_path = db.Column(db.String(255))
    heatmap_path = db.Column(db.String(255))
    model_version = db.Column(db.String(64))
    is_stub = db.Column(db.Boolean, nullable=False, default=False)
    # review_status: none | pending | confirmed | corrected
    review_status = db.Column(db.String(16), nullable=False, default="none", index=True)
    confirmed_label = db.Column(db.String(64))
    is_simulated = db.Column(db.Boolean, nullable=False, default=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    plot = db.relationship("Plot")

    @property
    def effective_label(self):
        return self.confirmed_label or self.diagnosis

    def to_dict(self):
        return {
            "id": self.id, "plot_id": self.plot_id, "crop": self.crop, "diagnosis": self.diagnosis,
            "confidence": self.confidence, "top3": self.top3, "severity": self.severity,
            "lat": self.lat, "lon": self.lon, "grid_cell": self.grid_cell, "region": self.region,
            "image_url": f"/api/scans/{self.id}/image" if self.image_path else None,
            "heatmap_url": f"/api/scans/{self.id}/heatmap" if self.heatmap_path else None,
            "model_version": self.model_version, "is_stub": self.is_stub,
            "review_status": self.review_status, "confirmed_label": self.confirmed_label,
            "is_simulated": self.is_simulated, "created_at": self.created_at.isoformat() + "Z",
        }


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    # role: farmer | expert
    role = db.Column(db.String(16), nullable=False, default="farmer")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "role": self.role}


class ConfirmedLabel(db.Model):
    __tablename__ = "confirmed_labels"
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("scans.id"), nullable=False, unique=True)
    crop = db.Column(db.String(20), nullable=False)
    label = db.Column(db.String(64), nullable=False)
    model_label = db.Column(db.String(64), nullable=False)
    reviewer = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class DiseaseProfile(db.Model):
    __tablename__ = "disease_profiles"
    id = db.Column(db.Integer, primary_key=True)
    crop = db.Column(db.String(20), nullable=False)
    disease = db.Column(db.String(64), nullable=False)
    name_en = db.Column(db.String(80), nullable=False)
    name_ms = db.Column(db.String(80), nullable=False)
    spread_mode = db.Column(db.String(16), nullable=False)
    weather_model = db.Column(db.String(16), nullable=False)
    temp_min = db.Column(db.Float)
    temp_max = db.Column(db.Float)
    moisture = db.Column(db.JSON)
    advice_type = db.Column(db.String(24), nullable=False)
    spread_radius_km = db.Column(db.Float, nullable=False, default=5)
    report_decay_days = db.Column(db.Float, nullable=False, default=14)
    source_refs = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint("crop", "disease", name="uq_profile_crop_disease"),)

    def to_dict(self):
        return {
            "crop": self.crop, "disease": self.disease, "name": {"en": self.name_en, "ms": self.name_ms},
            "spread_mode": self.spread_mode, "weather_model": self.weather_model,
            "temp_min": self.temp_min, "temp_max": self.temp_max, "moisture": self.moisture,
            "advice_type": self.advice_type, "spread_radius_km": self.spread_radius_km,
            "report_decay_days": self.report_decay_days, "source_refs": self.source_refs,
        }


class FertiliserProduct(db.Model):
    __tablename__ = "fertiliser_products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    n = db.Column(db.Float, nullable=False)
    p2o5 = db.Column(db.Float, nullable=False)
    k2o = db.Column(db.Float, nullable=False)
    mgo = db.Column(db.Float, nullable=False, default=0)
    price_rm_per_kg = db.Column(db.Float)
    active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "n": self.n, "p2o5": self.p2o5, "k2o": self.k2o, "mgo": self.mgo,
            "price_rm_per_kg": self.price_rm_per_kg, "active": self.active,
        }


class CropRequirement(db.Model):
    __tablename__ = "crop_requirements"
    id = db.Column(db.Integer, primary_key=True)
    crop = db.Column(db.String(20), nullable=False)
    stage = db.Column(db.String(20), nullable=False)
    n = db.Column(db.Float, nullable=False)
    p2o5 = db.Column(db.Float, nullable=False)
    k2o = db.Column(db.Float, nullable=False)
    is_placeholder = db.Column(db.Boolean, nullable=False, default=True)
    source = db.Column(db.String(255))
    __table_args__ = (db.UniqueConstraint("crop", "stage", name="uq_requirement_crop_stage"),)

    def to_dict(self):
        return {
            "crop": self.crop, "stage": self.stage, "n": self.n, "p2o5": self.p2o5, "k2o": self.k2o,
            "is_placeholder": self.is_placeholder, "source": self.source,
        }


class Device(db.Model):
    """A field sensor node attached to a plot. is_simulated devices are labelled "Simulated device"."""

    __tablename__ = "devices"
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(64), nullable=False, unique=True)
    plot_id = db.Column(db.Integer, db.ForeignKey("plots.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    kind = db.Column(db.String(32), nullable=False, default="sensor")
    key_hash = db.Column(db.String(255), nullable=False)
    is_simulated = db.Column(db.Boolean, nullable=False, default=False)
    sim_state = db.Column(db.JSON)
    transport = db.Column(db.String(16))
    last_seen_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    plot = db.relationship("Plot")

    def to_dict(self):
        return {
            "id": self.id, "uid": self.uid, "plot_id": self.plot_id, "name": self.name, "kind": self.kind,
            "is_simulated": self.is_simulated, "transport": self.transport,
            "last_seen_at": self.last_seen_at.isoformat() + "Z" if self.last_seen_at else None,
        }


class SensorReading(db.Model):
    __tablename__ = "sensor_readings"
    __table_args__ = (db.Index("ix_sensor_readings_plot_ts", "plot_id", "ts"),)
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=False, index=True)
    plot_id = db.Column(db.Integer, db.ForeignKey("plots.id"), nullable=False)
    ts = db.Column(db.DateTime, nullable=False)
    soil_moisture_pct = db.Column(db.Float)
    soil_temp_c = db.Column(db.Float)
    air_temp_c = db.Column(db.Float)
    air_rh_pct = db.Column(db.Float)
    soil_ec_ds_m = db.Column(db.Float)
    light_lux = db.Column(db.Float)
    battery_pct = db.Column(db.Float)
    leaf_wet = db.Column(db.Boolean)
    is_simulated = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    METRICS = ("soil_moisture_pct", "soil_temp_c", "air_temp_c", "air_rh_pct",
               "soil_ec_ds_m", "light_lux", "battery_pct", "leaf_wet")

    def to_dict(self):
        return {"ts": self.ts.isoformat() + "Z", "device_id": self.device_id, "is_simulated": self.is_simulated,
                **{m: getattr(self, m) for m in self.METRICS}}


class DeviceCommand(db.Model):
    """One watering/fertiliser command and its safety checks, confirmation and device acknowledgement."""

    __tablename__ = "device_commands"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(40), nullable=False, unique=True)
    plot_id = db.Column(db.Integer, db.ForeignKey("plots.id"), nullable=False, index=True)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=False, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("control_schedules.id"), nullable=True)
    action = db.Column(db.String(16), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(8), nullable=False)
    params = db.Column(db.JSON)
    source = db.Column(db.String(16), nullable=False, default="manual")
    status = db.Column(db.String(24), nullable=False, index=True)
    checks = db.Column(db.JSON)
    transport = db.Column(db.String(16))
    is_simulated = db.Column(db.Boolean, nullable=False, default=False)
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    result = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    confirmed_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

    device = db.relationship("Device")
    plot = db.relationship("Plot")

    def to_dict(self):
        def ts(v):
            return v.isoformat() + "Z" if v else None

        return {
            "id": self.id, "request_id": self.request_id, "plot_id": self.plot_id, "device_id": self.device_id,
            "device": self.device.name if self.device else None, "schedule_id": self.schedule_id,
            "action": self.action, "amount": self.amount, "unit": self.unit, "params": self.params,
            "source": self.source, "status": self.status, "checks": self.checks or [], "transport": self.transport,
            "is_simulated": self.is_simulated, "result": self.result, "created_at": ts(self.created_at),
            "confirmed_at": ts(self.confirmed_at), "sent_at": ts(self.sent_at),
            "completed_at": ts(self.completed_at), "expires_at": ts(self.expires_at),
        }


class ControlSchedule(db.Model):
    """A repeating watering/fertiliser routine at a local (MYT) time on chosen weekdays."""

    __tablename__ = "control_schedules"
    id = db.Column(db.Integer, primary_key=True)
    plot_id = db.Column(db.Integer, db.ForeignKey("plots.id"), nullable=False, index=True)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=True)
    action = db.Column(db.String(16), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    time_local = db.Column(db.String(5), nullable=False)
    days = db.Column(db.String(7), nullable=False, default="0123456")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    last_run_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    plot = db.relationship("Plot")

    def to_dict(self):
        return {
            "id": self.id, "plot_id": self.plot_id, "device_id": self.device_id, "action": self.action,
            "amount": self.amount, "time_local": self.time_local, "days": self.days, "enabled": self.enabled,
            "last_run_date": self.last_run_date.isoformat() if self.last_run_date else None,
        }


class HarvestRecord(db.Model):
    """A harvest the farmer logged for a plot – the yield outcome the Phase 14 learning compares routines against."""

    __tablename__ = "harvest_records"
    id = db.Column(db.Integer, primary_key=True)
    plot_id = db.Column(db.Integer, db.ForeignKey("plots.id"), nullable=False, index=True)
    harvested_on = db.Column(db.Date, nullable=False)
    kg = db.Column(db.Float, nullable=False)
    notes = db.Column(db.String(200))
    is_simulated = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id, "plot_id": self.plot_id, "harvested_on": self.harvested_on.isoformat(), "kg": self.kg,
            "notes": self.notes, "is_simulated": self.is_simulated, "created_at": self.created_at.isoformat() + "Z",
        }
