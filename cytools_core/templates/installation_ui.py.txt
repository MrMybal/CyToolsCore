"""Optional ImGui storage controls. Core owns the implementation, not this UI."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
_storage = None
_draft = None
_message = ''
_cuda_path = ''
_future = None
_executor = None


def configure():
    global _message
    from cytools_core.shared_installation import InstallationStorage
    storage = InstallationStorage(ROOT)
    try: storage.apply_environment()
    except Exception as exc:
        # Keep Options available so a removed Toolkit or malformed setting can be repaired.
        _message = str(exc)
    return storage


def panel(native, tr, label):
    global _storage, _draft, _message, _cuda_path, _future, _executor
    from cytools_core.shared_installation import InstallationStorage
    if _storage is None: _storage = InstallationStorage(ROOT)
    native.separator()
    native.text(tr('Installation storage'))
    try:
        if _draft is None: _draft = _storage.configuration()
        modes = ('local','shared')
        changed, index = native.combo(label('Download cache'), modes.index(_draft['downloadMode']),
                                      [tr('Local to this Tool'),tr('Shared folder')])
        if changed: _draft['downloadMode'] = modes[index]
        _, _draft['sharedRoot'] = native.input_text(label('Shared installation folder'), _draft['sharedRoot'])
        native.text_wrapped(tr('The shared folder preference applies to this Windows/Linux user. Each Tool chooses whether to use it.'))
        if native.button(label('Save storage settings')):
            _storage.configure(download_mode=_draft['downloadMode'], shared_root=_draft['sharedRoot'])
            _message = 'Saved. Restart the Tool after current jobs finish.'
        native.text_wrapped(tr('Download cache: avoids repeated transfers. Python, PyTorch CUDA libraries and existing model installations remain local. No files are moved.'))
        native.text_wrapped(str(_storage.cache_root()))
        native.text(tr('Shared CUDA Toolkit'))
        native.text_wrapped(tr('Register an installed Toolkit to reuse its compiler. Select a version compatible with the engine. This does not replace the NVIDIA driver or PyTorch libraries.'))
        _, _cuda_path = native.input_text(label('CUDA Toolkit directory'), _cuda_path)
        native.begin_disabled(_future is not None)
        if native.button(label('Verify and register CUDA Toolkit')):
            if _executor is None: _executor = ThreadPoolExecutor(max_workers=1)
            _future = _executor.submit(_storage.register_cuda, _cuda_path)
        native.end_disabled()
        native.same_line()
        if native.button(label('Official CUDA downloads')):
            import webbrowser
            webbrowser.open('https://developer.nvidia.com/cuda-downloads')
        if _future is not None and _future.done():
            try:
                record = _future.result()
                _message = tr('Registered CUDA Toolkit')+' '+record['version']
            except Exception as exc: _message = str(exc)
            _future = None
        status = _storage.status()
        components = status['components']
        keys = ['']+[item['key'] for item in components]
        labels = [tr('Use engine defaults')]+[item['version']+' — '+item['path'] for item in components]
        selected = status['cudaComponent']
        if selected and selected not in keys:
            keys.append(selected); labels.append(tr('Selected CUDA Toolkit is unavailable'))
        changed, index = native.combo(label('CUDA Toolkit for this Tool'), keys.index(selected) if selected in keys else 0, labels)
        if changed:
            _storage.select_cuda(keys[index]); _message = 'Saved. Restart the Tool after current jobs finish.'
        native.text_wrapped(tr('Gated models still require your own account and license acceptance. Use the model installation tab; credentials never enter this shared folder.'))
    except Exception as exc:
        _message = str(exc)
    if _message: native.text_wrapped(tr(_message))


def cli():
    import argparse
    from cytools_core.shared_installation import InstallationStorage
    parser = argparse.ArgumentParser(description='CyTools local/shared installation storage')
    sub = parser.add_subparsers(dest='action',required=True)
    sub.add_parser('status')
    config = sub.add_parser('configure'); config.add_argument('--mode',choices=['local','shared'],required=True); config.add_argument('--shared-root')
    register = sub.add_parser('register-cuda'); register.add_argument('path')
    select = sub.add_parser('select-cuda'); select.add_argument('key',help='Registered key, or default')
    args = parser.parse_args(); storage = InstallationStorage(ROOT)
    try:
        if args.action == 'status': result = storage.status()
        elif args.action == 'configure': result = storage.configure(download_mode=args.mode,shared_root=args.shared_root)
        elif args.action == 'register-cuda': result = storage.register_cuda(args.path)
        else: result = storage.select_cuda('' if args.key=='default' else args.key)
        print(json.dumps(result,ensure_ascii=True)); return 0
    except Exception as exc:
        print(json.dumps({'state':'Failed','code':getattr(exc,'code',type(exc).__name__),'message':str(exc)},ensure_ascii=True)); return 1


if __name__ == '__main__': raise SystemExit(cli())
