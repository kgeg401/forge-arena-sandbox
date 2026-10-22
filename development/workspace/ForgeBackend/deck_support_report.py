"""Report every unsupported entry of an Arena-exported deck without launching."""
import argparse
import json
from pathlib import Path
from card_support import inspect_deck, load_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('deck', type=Path)
    parser.add_argument('--index', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.deck.stat().st_size > 262144:
        parser.error('Select a deck file under 256 KiB.')
    index = load_index(args.index)
    if index is None:
        parser.error('Build a fresh support index first.')
    report = inspect_deck(args.deck.read_text(encoding='utf-8-sig'), index)
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        if args.output.exists():
            parser.error('Choose a new report path; previous evidence is preserved.')
        args.output.write_text(payload, encoding='utf8')
    print(payload)


if __name__ == '__main__':
    main()
