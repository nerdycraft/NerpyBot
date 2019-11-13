"""
starting file for nerpybot
"""

import argparse
import subprocess
import sys

INTRO = ("==========================\n"
         "       - Nerpy Bot -      \n"
         "==========================\n")


def parse_arguments():
    """
    parser for starting arguments

    currently only supports auto restart
    """
    parser = argparse.ArgumentParser(description="-> NerpyBot <-")
    parser.add_argument("--auto-restart",
                        help="Autorestarts Nerpy in case of issues",
                        action="store_true")
    return parser.parse_args()


def run_bot(autorestart):
    """
    Starts the Main Loop of the program
    """

    interpreter = sys.executable

    cmd = (interpreter, "NerdyPy.py")

    while True:
        try:
            code = subprocess.call(cmd)
        except KeyboardInterrupt:
            code = 0
            break
        else:
            if code == 0:
                break
            elif code == 26:
                print("Restarting...")
                continue
            else:
                if not autorestart:
                    break

    print("Bot has been terminated. Exit code: %d" % code)


if __name__ == "__main__":
    print(INTRO)
    ARGS = parse_arguments()

    run_bot(autorestart=ARGS.auto_restart)
