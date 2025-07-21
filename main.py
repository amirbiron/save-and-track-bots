# main.py - מאחד את Save-me ואת Sabscriber-tracking עם טוקנים נפרדים
import asyncio
import os
from save_me import main as save_me_main
from subscriber_tracking import main as subscriber_tracking_main

async def run_save_me():
    os.environ["BOT_TOKEN"] = os.environ.get("BOT_TOKEN_SAVE_ME", "")
    await asyncio.to_thread(save_me_main)

async def run_subs_tracker():
    os.environ["BOT_TOKEN"] = os.environ.get("BOT_TOKEN_SUBS_TRACK", "")
    await asyncio.to_thread(subscriber_tracking_main)

async def run_all():
    await asyncio.gather(
        run_save_me(),
        run_subs_tracker()
    )

if __name__ == "__main__":
    asyncio.run(run_all())
