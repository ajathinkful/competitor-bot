from apscheduler.schedulers.background import BackgroundScheduler

# Create a singleton scheduler instance
scheduler = BackgroundScheduler()
scheduler.start()
