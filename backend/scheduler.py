from apscheduler.schedulers.background import BackgroundScheduler
from services import update_matches

scheduler = BackgroundScheduler()
scheduler.add_job(update_matches, "interval", seconds=90)
