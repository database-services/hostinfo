import psutil
import os
import json
import datetime
import pwd
import grp
import subprocess
import platform
import pkg_resources
import GPUtil

def gather_system_info():
    system_info = {
        'cpu': {
            'cpu_times': psutil.cpu_times()._asdict(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'cpu_count': psutil.cpu_count(logical=False),
            'cpu_count_logical': psutil.cpu_count(logical=True),
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            'cpu_stats': psutil.cpu_stats()._asdict()
        },
        'gpu': get_gpu_info(),
        'memory': {
            'virtual_memory': psutil.virtual_memory()._asdict(),
            'swap_memory': psutil.swap_memory()._asdict()
        },
        'disk': {
            'disk_partitions': [part._asdict() for part in psutil.disk_partitions()],
            'disk_usage': {part.mountpoint: psutil.disk_usage(part.mountpoint)._asdict() for part in psutil.disk_partitions()},
            'disk_io_counters': psutil.disk_io_counters()._asdict()
        },
        'network': {
            'net_io_counters': psutil.net_io_counters()._asdict(),
            'net_if_addrs': {iface: [addr._asdict() for addr in addrs] for iface, addrs in psutil.net_if_addrs().items()},
            'net_if_stats': {iface: stats._asdict() for iface, stats in psutil.net_if_stats().items()},
            'net_connections': [conn._asdict() for conn in psutil.net_connections()]
        },
        'users': [user._asdict() for user in psutil.users()],
        'boot_time': psutil.boot_time(),
        'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else None,
        'processes': []
    }

    for proc in psutil.process_iter(['pid', 'name', 'username', 'status', 'cpu_percent', 'cpu_times', 'memory_info', 'io_counters', 'num_threads', 'create_time', 'exe', 'cmdline']):
        try:
            proc_info = proc.info
            if 'cpu_times' in proc_info and proc_info['cpu_times'] is not None:
                proc_info['cpu_times'] = proc_info['cpu_times']._asdict()
            if 'memory_info' in proc_info and proc_info['memory_info'] is not None:
                proc_info['memory_info'] = proc_info['memory_info']._asdict()
            if 'io_counters' in proc_info and proc_info['io_counters'] is not None:
                proc_info['io_counters'] = proc_info['io_counters']._asdict()
            system_info['processes'].append(proc_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    return system_info



def gather_platform_info():
    platform_info = {
        'system': platform.system(),
        'node': platform.node(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'architecture': platform.architecture(),
        'platform': platform.platform(),
        'uname': platform.uname()._asdict(),
        'python_version': platform.python_version(),
        'python_build': platform.python_build(),
        'python_compiler': platform.python_compiler()
    }

    return platform_info


def gather_rpm_packages():
    rpm_packages = {}
    try:
        result = subprocess.run(['rpm', '-qa', '--queryformat', '%{NAME} %{VERSION}-%{RELEASE}\n'], capture_output=True, text=True, check=True)
        for line in result.stdout.split('\n'):
            if line:
                name, version = line.split(' ', 1)
                rpm_packages[name] = version
    except subprocess.CalledProcessError as e:
        print(f"Error gathering RPM packages: {e}")

    return rpm_packages


def gather_dpkg_packages():
    dpkg_packages = {}
    try:
        result = subprocess.run(['dpkg-query', '-W', '-f=${Package} ${Version}\n'], capture_output=True, text=True, check=True)
        for line in result.stdout.split('\n'):
            if line:
                name, version = line.split(' ', 1)
                dpkg_packages[name] = version
    except subprocess.CalledProcessError as e:
        print(f"Error gathering Debian packages: {e}")

    return dpkg_packages


def gather_installed_python_packages():
    """
    Gathers detailed information about all installed Python packages.

    Returns:
        dict: A dictionary containing detailed information about installed Python packages.
    """
    installed_packages = {}
    for dist in pkg_resources.working_set:
        package_info = {
            'version': dist.version,
            'location': dist.location,
            'requires': [str(req) for req in dist.requires()]
        }
        installed_packages[dist.project_name] = package_info
    return installed_packages



def check_linux_pkg_type():
    if os.path.exists('/usr/bin/rpm') or os.path.exists('/bin/rpm'):
        return 'RPM-based'
    elif os.path.exists('/usr/bin/dpkg') or os.path.exists('/bin/dpkg'):
        return 'Debian-based'
    elif os.path.exists('/etc/os-release'):
        with open('/etc/os-release') as f:
            os_release_info = f.read().lower()
            if 'debian' in os_release_info or 'ubuntu' in os_release_info:
                return 'debian'
            elif 'centos' in os_release_info or 'fedora' in os_release_info or 'rhel' in os_release_info:
                return 'rpm'
    return 'Unknown'


def read_sysctl_conf(file_path='/etc/sysctl.conf'):
    sysctl_conf = {}

    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        sysctl_conf[key.strip()] = value.strip()
    return sysctl_conf


def get_current_sysctl_values():
    sysctl_values = {}
    result = subprocess.run(['sysctl', '-a'], capture_output=True, text=True)

    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line:
                if '=' in line:
                    key, value = line.split('=', 1)
                    sysctl_values[key.strip()] = value.strip()
    return sysctl_values

def get_users_info():
    users_info = []
    for user in pwd.getpwall():
        info = {
            'username': user.pw_name,
            'user_id': user.pw_uid,
            'group_id': user.pw_gid,
            'home_directory': user.pw_dir,
            'shell': user.pw_shell,
            'gecos': user.pw_gecos
        }
        users_info.append(info)
    return users_info

def get_groups_info():
    groups_info = []
    for group in grp.getgrall():
        info = {
            'groupname': group.gr_name,
            'group_id': group.gr_gid,
            'members': group.gr_mem
        }
        groups_info.append(info)
    return groups_info



def get_gpu_info():
    gpus = GPUtil.getGPUs()
    gpus_info = []

    for gpu in gpus:
        info = {
            'id': gpu.id,
            'name': gpu.name,
            'driver_version': gpu.driver,
            'total_memory': f"{gpu.memoryTotal} MB",
            'free_memory': f"{gpu.memoryFree} MB",
            'used_memory': f"{gpu.memoryUsed} MB",
            'temperature': f"{gpu.temperature} °C",
            'load': f"{gpu.load * 100} %",
            'uuid': gpu.uuid
        }
        gpus_info.append(info)

    return gpus_info



master={}

if check_linux_pkg_type() == 'debian':
    master['dpkg_packages'] = gather_dpkg_packages()
elif check_linux_pkg_type() == 'rpm':
    master['rpm_packages'] = gather_rpm_packages()

master['python_packages'] = gather_installed_python_packages()
master['platform_info'] = gather_platform_info()
master['system_info'] = gather_system_info()
master['sysctl_conf'] = read_sysctl_conf()
master['current_sysctl'] = get_current_sysctl_values()
master['users'] = get_users_info()
master['groups'] = get_groups_info()

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = "hostinfo_"+timestamp+".json"
print(f"Writing hostinfo to {filename}")
with open(filename, "w") as f:
    f.write(json.dumps(master))
