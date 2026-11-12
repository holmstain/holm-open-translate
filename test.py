"""Optional, single-translation NVIDIA smoke check (up to three HTTP attempts); safe to import during discovery."""
import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Authorize one short translation (up to three HTTP attempts) using the configured project key')
    args = parser.parse_args()
    if not args.live:
        parser.print_help()
        return 0

    from app import API_KEY, translate_text
    if not API_KEY:
        print('NVIDIA_API_KEY is not configured.')
        return 1
    try:
        translated = translate_text('Hello', 'tr', 'en')
        if translated.casefold() == 'hello':
            print('Live smoke failed: the provider returned the unchanged English source.')
            return 1
    except Exception:
        # Provider exceptions can contain request data; never print them here.
        print('Live smoke failed. Check API configuration and network access.')
        return 1
    print('Live smoke passed: one complete English-to-Turkish translation received.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
