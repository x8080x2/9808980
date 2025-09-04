import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "fallback_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///wallet_monitor.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

# Initialize scheduler
scheduler = BackgroundScheduler()

with app.app_context():
    # Import models and routes
    import models
    import routes
    from wallet_monitor import start_monitoring
    
    # Create all tables
    db.create_all()
    
    # Start the monitoring scheduler
    if not scheduler.running:
        scheduler.start()
        start_monitoring(scheduler)
        atexit.register(lambda: scheduler.shutdown())

logging.basicConfig(level=logging.DEBUG)
