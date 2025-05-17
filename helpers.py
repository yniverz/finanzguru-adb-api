from builtins import print as _print
import datetime
import pytz


def print(*args, **kwargs):
    """
    Custom print function to add a timestamp to the output
    """
    time_now = datetime.datetime.now(pytz.timezone('Europe/Berlin'))
    time_str = time_now.strftime("%Y-%m-%d %H:%M:%S")
    _print(f"[{time_str}] ", end="")
    _print(*args, **kwargs)
