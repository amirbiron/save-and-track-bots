import asyncio
import os
from save_me import main as save_me_main
from subscriber_tracking import main as subscriber_tracking_main

# --- הרצת בוט Save Me ---
async def run_save_me():
    os.environ["BOT_TOKEN"] = os.environ.get("BOT_TOKEN_SAVE_ME", "")
    os.environ["MONGO_URI"] = os.environ.get("MONGO_URI", "")  # חובה שיהיה
    await asyncio.to_thread(save_me_main)

# --- הרצת בוט Subscriber Tracker ---
async def run_subs_tracker():
    os.environ["BOT_TOKEN"] = os.environ.get("BOT_TOKEN_SUBS_TRACK", "")
    os.environ["MONGO_URI"] = os.environ.get("MONGO_URI", "")  # גם פה חובה
    await asyncio.to_thread(subscriber_tracking_main)

# --- הרצת שניהם במקביל ---
async def run_all():
    await asyncio.gather(
        run_save_me(),
        run_subs_tracker()
    )

if __name__ == "__main__":
    asyncio.run(run_all())
