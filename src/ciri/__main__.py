"""python -m ciri bootstrap|train|generate"""

from __future__ import annotations

import argparse
import sys

from ciri.bootstrap import main as bootstrap_main
from ciri.data.generate import main as generate_main
from ciri.ml.train import main as train_main


def main() -> None:
    parser = argparse.ArgumentParser(description="Critical Infrastructure Risk Intelligence Platform")
    parser.add_argument("command", choices=["bootstrap", "generate", "train"])
    parser.add_argument("--tiny", action="store_true")
    args = parser.parse_args()
    if args.command == "bootstrap":
        sys.argv = ["bootstrap", "--tiny"] if args.tiny else ["bootstrap"]
        bootstrap_main()
    elif args.command == "generate":
        sys.argv = ["generate"]
        generate_main()
    else:
        sys.argv = ["train"]
        train_main()


if __name__ == "__main__":
    main()
