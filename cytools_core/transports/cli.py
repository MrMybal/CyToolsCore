"""Compatibility entry point; CyMCPSDK C++ owns CLI parsing and transports."""
import json
import sys
from ..errors import CyToolError


def run_cli(factory, argv=None):
    from ._native import NativeHost
    try:
        with NativeHost(factory) as host:
            return host.call('run_cli', argv=list(sys.argv[1:] if argv is None else argv))
    except CyToolError as exc:
        print(json.dumps({'error': exc.to_dict()}, ensure_ascii=False), file=sys.stderr)
        return 1
