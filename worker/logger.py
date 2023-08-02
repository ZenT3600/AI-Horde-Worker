import sys
import os
import json
import base64
import pickle
from PIL import Image
import io
from functools import partialmethod
from threading import Thread

from loguru import logger
from discord_webhook import DiscordWebhook, DiscordEmbed

STDOUT_LEVELS = ["GENERATION", "PROMPT"]
INIT_LEVELS = ["INIT", "INIT_OK", "INIT_WARN", "INIT_ERR"]
MESSAGE_LEVELS = ["MESSAGE"]
STATS_LEVELS = ["STATS"]
# By default we're at error level or higher
verbosity = 20
quiet = 0
webhook_url = {}
send_queue = []


def get_color_from_level(lvl):
    try:
        return {
            "GENERATION": ":purple_square:",
            "PROMPT": ":purple_square:",
            "INIT": ":white_large_square:",
            "INIT_OK": ":green_square:",
            "INIT_WARN": ":orange_square:",
            "INIT_ERR": ":red_square:",
            "ERROR": ":red_square:",
            "TRACE":":red_square:",
            "MESSAGE": ":green_square:",
            "STATS": ":blue_square:",
            "DEBUG": ":black_large_square:",
            "WARNING": ":orange_square:",
        }[lvl]
    except:
        return ":white_large_square:"


def set_discord_hook(channel, url):
    global webhook_url
    webhook_url[channel] = url


def send_via_discord(record):
    global webhook_url, send_queue

    msg = record["message"]
    lvl = record["level"].name
    color = get_color_from_level(lvl)
    time = str(record["time"])
    webhook = None
    if lvl == "PROMPT":
        webhook = DiscordWebhook(url=webhook_url["prompts"], rate_limit_retry=True)
        jobj = json.loads(msg)
        pobj = jobj["prompt"]
        if "###" not in pobj:
            pobj = f"{pobj} ### "
        prompt, negprompt = pobj.split("###", 1)
        embed = DiscordEmbed(
            title="Ungaretti could never...", description=prompt + "\n\n\n" + negprompt, color="ff00ff"
        )
        embed.set_thumbnail(url="https://cdn-0.emojis.wiki/emoji-pics/facebook/skull-facebook.png")
        embed.set_footer(text=repr({k: v for k, v in jobj.items() if k != "prompt"}))
        embed.set_timestamp()
        webhook.add_embed(embed)
        webhook.execute()
    elif lvl == "GENERATION":
        try:
            webhook = DiscordWebhook(url=webhook_url["prompts"], rate_limit_retry=True)
            jobj = json.loads(msg)
            image = pickle.loads(base64.b64decode(jobj["image"]))
            fname = jobj["seed"] + ".png"
            image.save(fname)
            pobj = jobj["prompt"]
            if "###" not in pobj:
                pobj = f"{pobj} ### "
            prompt, negprompt = pobj.split("###", 1)
            embed = DiscordEmbed(
                title="It has been done...", description=prompt + "\n\n\n" + negprompt, color="ff00ff"
            )
            embed.set_thumbnail(url="https://cdn-0.emojis.wiki/emoji-pics/facebook/skull-facebook.png")
            embed.set_footer(text=repr({k: v for k, v in jobj.items() if k != "prompt"}))
            embed.set_timestamp()
            with open(fname, "rb") as f:
                webhook.add_file(file=f.read(), filename=fname)
            webhook.add_embed(embed)
            webhook.execute()
        except:
            return
    else:
        send_queue.append(f"[**{color} {lvl} {color}**] ~ {msg}")
        if len(send_queue) < 10:
            return
        webhook = DiscordWebhook(url=webhook_url["logs"], rate_limit_retry=True, content="\n".join(send_queue))
        send_queue.clear()
        webhook.execute()


def set_logger_verbosity(count):
    global verbosity
    # The count comes reversed. So count = 0 means minimum verbosity
    # While count 5 means maximum verbosity
    # So the more count we have, the lowe we drop the versbosity maximum
    verbosity = 20 - (count * 10)


def quiesce_logger(count):
    global quiet
    # The bigger the count, the more silent we want our logger
    quiet = count * 10


def is_stdout_log(record):
    if record["level"].name not in STDOUT_LEVELS:
        return False
    if record["level"].no < verbosity + quiet:
        return False
    return True


def is_init_log(record):
    if record["level"].name not in INIT_LEVELS:
        return False
    if record["level"].no < verbosity + quiet:
        return False
    return True


def is_msg_log(record):
    if record["level"].name not in MESSAGE_LEVELS:
        return False
    if record["level"].no < verbosity + quiet:
        return False
    return True


def is_stderr_log(record):
    if record["level"].name in STDOUT_LEVELS + INIT_LEVELS + MESSAGE_LEVELS + STATS_LEVELS:
        return False
    if record["level"].no < verbosity + quiet:
        return False
    return True


def is_stats_log(record):
    if record["level"].name not in STATS_LEVELS:
        return False
    return True


def is_not_stats_log(record):
    if record["level"].name in STATS_LEVELS:
        return False
    return True


def is_trace_log(record):
    if record["level"].name not in ["TRACE", "ERROR"]:
        return False
    return True


def test_logger():
    logger.generation(
        "This is a generation message\nIt is typically multiline\nThee Lines".encode("unicode_escape").decode("utf-8"),
    )
    logger.prompt("This is a prompt message")
    logger.debug("Debug Message")
    logger.info("Info Message")
    logger.warning("Info Warning")
    logger.error("Error Message")
    logger.critical("Critical Message")
    logger.init("This is an init message", status="Starting")
    logger.init_ok("This is an init message", status="OK")
    logger.init_warn("This is an init message", status="Warning")
    logger.init_err("This is an init message", status="Error")
    logger.message("This is user message")
    sys.exit()


logfmt = (
    "<level>{level: <10}</level> | <green>{time:YYYY-MM-DD HH:mm:ss.SSSSSS}</green> | "
    "<green>{name}</green>:<green>{function}</green>:<green>{line}</green> - <level>{message}</level>"
)
genfmt = "<level>{level: <10}</level> @ <green>{time:YYYY-MM-DD HH:mm:ss.SSSSSS}</green> | <level>{message}</level>"
initfmt = "<magenta>INIT      </magenta> | <level>{extra[status]: <11}</level> | <magenta>{message}</magenta>"
msgfmt = "<level>{level: <10}</level> | <level>{message}</level>"

try:
    logger.level("GENERATION", no=24, color="<cyan>")
    logger.level("PROMPT", no=23, color="<yellow>")
    logger.level("INIT", no=31, color="<white>")
    logger.level("INIT_OK", no=31, color="<green>")
    logger.level("INIT_WARN", no=31, color="<yellow>")
    logger.level("INIT_ERR", no=31, color="<red>")
    # Messages contain important information without which this application might not be able to be used
    # As such, they have the highest priority
    logger.level("MESSAGE", no=61, color="<green>")
    # Stats are info that might not display well in the terminal
    logger.level("STATS", no=19, color="<blue>")
except TypeError:
    pass

logger = logger.patch(lambda r: Thread(target=send_via_discord, args=(r,), daemon=True).start())

logger.__class__.generation = partialmethod(logger.__class__.log, "GENERATION")
logger.__class__.prompt = partialmethod(logger.__class__.log, "PROMPT")
logger.__class__.init = partialmethod(logger.__class__.log, "INIT")
logger.__class__.init_ok = partialmethod(logger.__class__.log, "INIT_OK")
logger.__class__.init_warn = partialmethod(logger.__class__.log, "INIT_WARN")
logger.__class__.init_err = partialmethod(logger.__class__.log, "INIT_ERR")
logger.__class__.message = partialmethod(logger.__class__.log, "MESSAGE")
logger.__class__.stats = partialmethod(logger.__class__.log, "STATS")

config = {
    "handlers": [
        {
            "sink": sys.stderr,
            "format": logfmt,
            "colorize": True,
            "filter": is_stderr_log,
        },
        {
            "sink": sys.stdout,
            "format": genfmt,
            "level": "PROMPT",
            "colorize": True,
            "filter": is_stdout_log,
        },
        {
            "sink": sys.stdout,
            "format": initfmt,
            "level": "INIT",
            "colorize": True,
            "filter": is_init_log,
        },
        {
            "sink": sys.stdout,
            "format": msgfmt,
            "level": "MESSAGE",
            "colorize": True,
            "filter": is_msg_log,
        },
        {
            "sink": "logs/bridge.log",
            "format": logfmt,
            "level": "DEBUG",
            "colorize": False,
            "filter": is_not_stats_log,
            "retention": "2 days",
            "rotation": "3 hours",
        },
        {
            "sink": "logs/stats.log",
            "format": logfmt,
            "level": "STATS",
            "colorize": False,
            "filter": is_stats_log,
            "retention": "7 days",
            "rotation": "1 days",
        },
        {
            "sink": "logs/trace.log",
            "format": logfmt,
            "level": "TRACE",
            "colorize": False,
            "filter": is_trace_log,
            "retention": "3 days",
            "rotation": "1 days",
            "backtrace": True,
            "diagnose": True,
        },
    ],
}
logger.configure(**config)
