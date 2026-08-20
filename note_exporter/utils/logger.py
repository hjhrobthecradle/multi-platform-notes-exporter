import sys

class Logger:
    @staticmethod
    def info(msg: str):
        print(f"\033[94m[*] {msg}\033[0m")

    @staticmethod
    def success(msg: str):
        print(f"\033[92m[+] {msg}\033[0m")

    @staticmethod
    def warn(msg: str):
        print(f"\033[93m[!] {msg}\033[0m")

    @staticmethod
    def error(msg: str):
        print(f"\033[91m[-] {msg}\033[0m", file=sys.stderr)

    @staticmethod
    def header(msg: str):
        print(f"\n\033[1;96m=== {msg} ===\033[0m")
