from loguru import logger

from .cli import PipZapCLI


def main():
    cli = PipZapCLI()
    try:
        cli.run()
    except Exception as e:
        logger.error(f"PipZap encountered an error: {e}")


if __name__ == "__main__":
    main()
