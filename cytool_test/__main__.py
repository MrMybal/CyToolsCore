from . import create_runtime
from cytools_core.transports.cli import run_cli

def main():
    raise SystemExit(run_cli(create_runtime))

if __name__=='__main__': main()
