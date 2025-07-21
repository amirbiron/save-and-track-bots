
# main.py - מאחד את Save-me ואת Sabscriber-tracking
import asyncio
from save_me import main as save_me_main
from subscriber_tracking import main as subscriber_tracking_main

async def run_all():
    await asyncio.gather(
        asyncio.to_thread(save_me_main),
        asyncio.to_thread(subscriber_tracking_main)
    )

if __name__ == "__main__":
    asyncio.run(run_all())
