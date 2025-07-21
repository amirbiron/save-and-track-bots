# main.py
import asyncio
import os
from multiprocessing import Process
from save_me import main as save_me_main
from subscriber_tracking import main as subscriber_tracking_main

def run_save_me():
    os.environ["BOT_TOKEN"] = os.environ.get("BOT_TOKEN_SAVE_ME", "")
    save_me_main()

def run_subs_tracker():
    os.environ["BOT_TOKEN"] = os.environ.get("BOT_TOKEN_SUBS_TRACK", "")
    subscriber_tracking_main()

if __name__ == "__main__":
    p1 = Process(target=run_save_me)
    p2 = Process(target=run_subs_tracker)
    p1.start()
    p2.start()
    p1.join()
    p2.join()
