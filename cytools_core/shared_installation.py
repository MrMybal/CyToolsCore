"""Opt-in per-user download storage and explicitly selected CUDA toolkits.

No environment or filesystem changes on import. Python environments and drivers
are never installed, moved, shared, or upgraded by this module.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import uuid

from .errors import CyToolError
from .storage import RuntimeLock


def settings_directory():
    override = os.environ.get('CYTOOLS_SETTINGS_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'CyTools'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'cytools'


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text('utf-8'))
    except FileNotFoundError:
        return default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', 'utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class InstallationStorage:
    def __init__(self, tool_root):
        self.tool_root = Path(tool_root).resolve()
        self.local_settings = self.tool_root/'data/settings/installation-storage.json'
        self.global_settings = settings_directory()/'installation-storage.json'

    def configuration(self):
        global_value = read_json(self.global_settings, {})
        local_value = read_json(self.local_settings, {})
        from .schema import validate_document
        if self.global_settings.exists(): validate_document(global_value, 'installation-storage')
        if self.local_settings.exists(): validate_document(local_value, 'installation-storage')
        mode = local_value.get('downloadMode', 'local')
        if mode not in ('local', 'shared'):
            raise ValueError('Unknown download storage mode')
        root = Path(global_value.get('sharedRoot', str(settings_directory()/'shared'))).expanduser()
        if not root.is_absolute():
            raise ValueError('Shared storage path must be absolute')
        return {'schemaVersion': 1, 'downloadMode': mode, 'sharedRoot': str(root.resolve()),
                'cudaComponent': local_value.get('cudaComponent', '')}

    def configure(self, *, download_mode, shared_root=None):
        if download_mode not in ('local', 'shared'):
            raise ValueError('Unknown download storage mode')
        if shared_root is not None:
            root = Path(shared_root).expanduser()
            if not root.is_absolute():
                raise ValueError('Shared storage path must be absolute')
            # Test writability before committing preferences; never move existing data.
            root.mkdir(parents=True, exist_ok=True)
            probe = root/('.cytools-write-'+uuid.uuid4().hex)
            try:
                with probe.open('x') as stream: stream.write('')
            finally:
                probe.unlink(missing_ok=True)
            write_json(self.global_settings, {'schemaVersion': 1, 'sharedRoot': str(root.resolve())})
        current = read_json(self.local_settings, {})
        write_json(self.local_settings, {**current, 'schemaVersion': 1, 'downloadMode': download_mode})
        return self.status()

    def cache_root(self):
        config = self.configuration()
        return (Path(config['sharedRoot'])/'downloads' if config['downloadMode']=='shared'
                else self.tool_root/'runtime/download-cache')

    def environment(self):
        """Process-local overrides for known clients, never HF_HOME (credentials)."""
        root = self.cache_root()
        result = {'PIP_CACHE_DIR': str(root/'pip'), 'HF_HUB_CACHE': str(root/'huggingface/hub'),
                  'HUGGINGFACE_HUB_CACHE': str(root/'huggingface/hub'),
                  'TORCH_HOME': str(root/'torch'),
                  'CYTOOLS_DOWNLOAD_CACHE': str(root/'verified') if self.configuration()['downloadMode']=='shared' else ''}
        selected = self.configuration()['cudaComponent']
        if selected:
            component = self.component(selected)
            path = Path(component['path'])
            executable = path/'bin'/('nvcc.exe' if os.name=='nt' else 'nvcc')
            if not executable.is_file():
                raise CyToolError('DependencyMissing', 'Selected CUDA Toolkit is no longer available')
            with executable.open('rb') as stream:
                actual = hashlib.file_digest(stream,'sha256').hexdigest()
            if actual != component['compilerSha256']:
                raise CyToolError('DependencyChanged', 'CUDA Toolkit compiler changed; register and select it again')
            result.update(CUDA_PATH=str(path), CUDA_HOME=str(path))
            result['PATH'] = str(path/'bin')+os.pathsep+os.environ.get('PATH','')
        return result

    def apply_environment(self):
        os.environ.update(self.environment())

    def registry(self):
        return Path(self.configuration()['sharedRoot'])/'components'

    def component(self, key):
        if not re.fullmatch('[a-f0-9]{64}', key):
            raise ValueError('Invalid component key')
        value = read_json(self.registry()/(key+'.json'), None)
        if value is None:
            raise CyToolError('DependencyMissing', 'Shared component is not registered')
        if value.get('platform') != platform.system() or value.get('architecture') != platform.machine():
            raise CyToolError('UnsupportedPlatform', 'Component platform does not match this computer')
        return value

    def register_cuda(self, path):
        root = Path(path).expanduser()
        if not root.is_absolute(): raise ValueError('CUDA Toolkit path must be absolute')
        root = root.resolve()
        executable = root/'bin'/('nvcc.exe' if os.name=='nt' else 'nvcc')
        if not executable.is_file() or not (root/'include/cuda.h').is_file():
            raise ValueError('Select a CUDA Toolkit directory containing bin/nvcc and include/cuda.h')
        kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
        result = subprocess.run([str(executable), '--version'], capture_output=True, text=True,
                                timeout=10, check=True, **kwargs)
        match = re.search(r'release\s+(\d+\.\d+).*?V(\d+\.\d+\.\d+)', result.stdout, re.S)
        if not match: raise ValueError('Could not identify CUDA Toolkit version')
        with executable.open('rb') as stream:
            compiler_hash = hashlib.file_digest(stream,'sha256').hexdigest()
        value = {'schemaVersion': 1, 'kind': 'cuda-toolkit', 'version': match[2],
                 'platform': platform.system(), 'architecture': platform.machine(),
                 'path': str(root), 'compilerSha256': compiler_hash,
                 'source': 'https://developer.nvidia.com/cuda-downloads',
                 'mode': 'shared-installation', 'managed': False}
        key = digest(value)
        write_json(self.registry()/(key+'.json'), value)
        return {'key': key, **value}

    def select_cuda(self, key):
        if key: self.component(key)
        current = read_json(self.local_settings, {})
        write_json(self.local_settings, {**current, 'schemaVersion': 1, 'cudaComponent': key})
        return {'state': 'RestartRequired', 'cudaComponent': key}

    def status(self):
        config = self.configuration()
        components = []
        for path in sorted(self.registry().glob('*.json')):
            try: components.append({'key': path.stem, **self.component(path.stem)})
            except (ValueError, CyToolError): continue
        return {**config, 'cacheRoot': str(self.cache_root()), 'components': components,
                'pythonMode': 'tool-local', 'modelsMode': 'existing-tool-installation',
                'driverMode': 'system', 'pytorchCudaMode': 'tool-local',
                'settingsFile': str(self.global_settings),
                'restartRequiredAfterChange': True}

    @contextmanager
    def artifact_lock(self, sha256):
        if not re.fullmatch('[a-fA-F0-9]{64}', sha256): raise ValueError('SHA256 required')
        folder = self.cache_root()/'verified'/sha256.lower()
        folder.mkdir(parents=True, exist_ok=True)
        lock = RuntimeLock(folder/'download.lock')
        try: yield folder
        finally: lock.close()

    def download(self, url, *, sha256, size=None, license_accepted=True, **options):
        """Verified download cache; does not execute installers or accept terms."""
        from .downloads import DownloadManager
        if not license_accepted:
            return {'state':'LicenseAcceptanceRequired', 'source':url,
                    'action':'Accept the official terms personally, then retry.'}
        try:
            with self.artifact_lock(sha256) as folder:
                return DownloadManager(folder, use_shared_cache=False).download('artifact', url, sha256=sha256, size=size, **options)
        except CyToolError as exc:
            if exc.code == 'AuthenticationRequired':
                return {'state':'AccessRequired', 'source':url,
                        'action':'Connect your local account and check license/access approval, then retry.'}
            raise


def register_operations(runtime, tool_root):
    """Expose read-only installation state through the Tool's existing CLI/MCP."""
    identifier = 'installation_storage_status'
    if any(op['id']==identifier for op in runtime.descriptor['operations']): return
    operation = {'id':identifier, 'name':'Installation storage status',
        'description':'Local/shared caches and registered CUDA Toolkits; does not install anything.',
        'inputSchema':{'type':'object','properties':{},'additionalProperties':False},
        'outputSchema':{'type':'object'}, 'resourceRequirements':{}, 'supportedBackends':[],
        'permissions':[], 'canRunAsync':True,'canCancel':False,'supportsProgress':False}
    from .schema import validate_manifest
    descriptor = {**runtime.descriptor, 'operations':[*runtime.descriptor['operations'],operation]}
    validate_manifest(descriptor)
    runtime.descriptor = descriptor
    runtime.register(identifier, lambda context, parameters: InstallationStorage(tool_root).status())
