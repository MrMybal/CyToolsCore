"""Portable measurements and a conservative, per-runtime reservation ledger."""
import copy
import os
import platform
import shutil
import subprocess
import threading
import psutil
from .errors import CyToolError
from .schema import validate_document


def _gpu_process_environment():
    """NVML needs ProgramFiles on Windows; MCP clients may omit it."""
    environment=dict(os.environ)
    if os.name=='nt' and not any(k.casefold()=='programfiles' and v for k,v in environment.items()):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows\CurrentVersion') as key:
                value,_=winreg.QueryValueEx(key,'ProgramFilesDir')
            if isinstance(value,str) and os.path.isdir(value):environment['ProgramFiles']=value
        except (OSError,ImportError):pass
    return environment


def system_resources(path='.'):
    memory = psutil.virtual_memory()
    gpus = []
    # Optional provider. No NVIDIA dependency and no claim about unseen devices.
    executable = shutil.which('nvidia-smi')
    if executable:
        try:
            result = subprocess.run([executable, '--query-gpu=index,name,memory.total,memory.free', '--format=csv,noheader,nounits'],
                                    capture_output=True, text=True, timeout=3, check=True,env=_gpu_process_environment())
            for line in result.stdout.splitlines():
                index, name, total, free = [v.strip() for v in line.split(',')]
                gpus.append({'id':index, 'name':name, 'vendor':'NVIDIA', 'vramTotalBytes':int(total)*1048576,
                             'vramFreeBytes':int(free)*1048576, 'computeBackends':['CUDA'], 'source':'nvidia-smi'})
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    architecture = {'amd64':'x64','x86_64':'x64','aarch64':'ARM64','arm64':'ARM64'}.get(platform.machine().lower(), platform.machine())
    return {'os':{'Darwin':'macOS'}.get(platform.system(), platform.system()), 'osVersion':platform.release(),
            'architecture':architecture, 'cpu':platform.processor(), 'cpuThreads':psutil.cpu_count() or 1,
            'cpuCores':psutil.cpu_count(logical=False), 'ramTotalBytes':memory.total, 'ramFreeBytes':memory.available,
            'diskFreeBytes':shutil.disk_usage(path).free, 'gpus':gpus, 'gpuDiscoveryComplete':False,
            'computeBackends':['CPU'] + (['CUDA'] if gpus else [])}


def platform_status(entries, current):
    if not entries:
        return 'Unknown'
    matches = [e for e in entries if e['os'] == current['os'] and e['architecture'] == current['architecture']]
    if not matches:
        return 'Unsupported'
    # Minimum OS version cannot be safely compared to marketing names: fail closed.
    for entry in matches:
        if entry.get('minimumOSVersion') and entry['minimumOSVersion'] != current.get('osVersion'):
            continue
        if entry.get('computeBackends') and not set(entry['computeBackends']) & set(current['computeBackends']):
            continue
        if entry['status'] in ('Supported', 'Experimental'):
            return entry['status']
    return 'Unsupported' if any(e['status']=='Unsupported' for e in matches) else 'Unknown'


class ResourceLedger:
    """Reservation ownership is explicit. All quantities are bytes, never GB strings."""
    def __init__(self, capacity):
        self.capacity = copy.deepcopy(capacity)
        self._held = {}
        self._lock = threading.RLock()

    def _available(self):
        result = copy.deepcopy(self.capacity)
        for value in self._held.values():
            for key in ('ramBytes','diskBytes','cpuThreads'):
                result[key] = result.get(key, 0) - value.get(key, 0)
            for device, amount in value.get('vramBytes', {}).items():
                result.setdefault('vramBytes', {})[device] -= amount
        return result

    def normalize(self, value):
        validate_document(value, 'resources')
        result = copy.deepcopy(value)
        result['diskBytes'] = result.get('diskBytes',0) + result.get('temporaryDiskBytes',0)
        result.pop('temporaryDiskBytes', None)
        return result

    @staticmethod
    def shortage(needed, available):
        for key, code in [('ramBytes','InsufficientRAM'), ('diskBytes','InsufficientDisk'), ('cpuThreads','UnsupportedCPU')]:
            if needed.get(key,0) > available.get(key,0):
                return code
        if any(amount > available.get('vramBytes',{}).get(device,0) for device,amount in needed.get('vramBytes',{}).items()):
            return 'InsufficientVRAM'
        return None

    def reserve(self, owner, requirements):
        requirements = self.normalize(requirements)
        with self._lock:
            if owner in self._held:
                raise CyToolError('InvalidState', 'Reservation owner already exists')
            if self.shortage(requirements, self._available()):
                return False
            self._held[owner] = requirements
            return True

    def release(self, owner):
        with self._lock:
            return self._held.pop(owner, None)

    def snapshot(self):
        with self._lock:
            return {'capacity':copy.deepcopy(self.capacity), 'available':self._available(), 'reservations':copy.deepcopy(self._held)}
