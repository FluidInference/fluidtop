import os
import glob
import subprocess
from subprocess import PIPE
import psutil
from .parsers import *
import plistlib


def parse_powermetrics(path='/tmp/fluidtop_powermetrics', timecode="0"):
    data = None
    try:
        with open(path+timecode, 'rb') as fp:
            data = fp.read()
        data = data.split(b'\x00')
        powermetrics_parse = plistlib.loads(data[-1])
        thermal_pressure = parse_thermal_pressure(powermetrics_parse)
        cpu_metrics_dict = parse_cpu_metrics(powermetrics_parse)
        gpu_metrics_dict = parse_gpu_metrics(powermetrics_parse)
        bandwidth_metrics = None
        timestamp = powermetrics_parse["timestamp"]
        return cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, bandwidth_metrics, timestamp
    except Exception as e:
        if data:
            if len(data) > 1:
                powermetrics_parse = plistlib.loads(data[-2])
                thermal_pressure = parse_thermal_pressure(powermetrics_parse)
                cpu_metrics_dict = parse_cpu_metrics(powermetrics_parse)
                gpu_metrics_dict = parse_gpu_metrics(powermetrics_parse)
                bandwidth_metrics = None
                timestamp = powermetrics_parse["timestamp"]
                return cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, bandwidth_metrics, timestamp
        return False


def clear_console():
    command = 'clear'
    os.system(command)


def convert_to_GB(value):
    return round(value/1024/1024/1024, 1)


def run_powermetrics_process(timecode, nice=10, interval=1000):
    #ver, *_ = platform.mac_ver()
    #major_ver = int(ver.split(".")[0])
    for tmpf in glob.glob("/tmp/fluidtop_powermetrics*"):
        os.remove(tmpf)
    output_file_flag = "-o"
    command = " ".join([
        "sudo nice -n",
        str(nice),
        "powermetrics",
        "--samplers cpu_power,gpu_power,thermal",
        output_file_flag,
        "/tmp/fluidtop_powermetrics"+timecode,
        "-f plist",
        "-i",
        str(interval)
    ])
    process = subprocess.Popen(command.split(" "), stdin=PIPE, stdout=PIPE)
    return process


def get_ram_metrics_dict():
    ram_metrics = psutil.virtual_memory()
    swap_metrics = psutil.swap_memory()
    total_GB = convert_to_GB(ram_metrics.total)
    free_GB = convert_to_GB(ram_metrics.available)
    used_GB = convert_to_GB(ram_metrics.total-ram_metrics.available)
    swap_total_GB = convert_to_GB(swap_metrics.total)
    swap_used_GB = convert_to_GB(swap_metrics.used)
    swap_free_GB = convert_to_GB(swap_metrics.total-swap_metrics.used)
    if swap_total_GB > 0:
        swap_free_percent = int(100-(swap_free_GB/swap_total_GB*100))
    else:
        swap_free_percent = None
    ram_metrics_dict = {
        "total_GB": round(total_GB, 1),
        "free_GB": round(free_GB, 1),
        "used_GB": round(used_GB, 1),
        "free_percent": int(100-(ram_metrics.available/ram_metrics.total*100)),
        "swap_total_GB": swap_total_GB,
        "swap_used_GB": swap_used_GB,
        "swap_free_GB": swap_free_GB,
        "swap_free_percent": swap_free_percent,
    }
    return ram_metrics_dict


def get_cpu_info():
    cpu_info = os.popen('sysctl -a | grep machdep.cpu').read()
    cpu_info_lines = cpu_info.split("\n")
    data_fields = ["machdep.cpu.brand_string", "machdep.cpu.core_count"]
    cpu_info_dict = {}
    for l in cpu_info_lines:
        for h in data_fields:
            if h in l:
                value = l.split(":")[1].strip()
                cpu_info_dict[h] = value
    return cpu_info_dict


def get_core_counts():
    cores_info = os.popen('sysctl -a | grep hw.perflevel').read()
    cores_info_lines = cores_info.split("\n")
    data_fields = ["hw.perflevel0.logicalcpu", "hw.perflevel1.logicalcpu"]
    cores_info_dict = {}
    for l in cores_info_lines:
        for h in data_fields:
            if h in l:
                value = int(l.split(":")[1].strip())
                cores_info_dict[h] = value
    return cores_info_dict


def get_gpu_cores():
    try:
        cores = os.popen(
            "system_profiler -detailLevel basic SPDisplaysDataType | grep 'Total Number of Cores'").read()
        cores = int(cores.split(": ")[-1])
    except:
        cores = "?"
    return cores


def get_soc_info():
    cpu_info_dict = get_cpu_info()
    core_counts_dict = get_core_counts()
    try:
        e_core_count = core_counts_dict["hw.perflevel1.logicalcpu"]
        p_core_count = core_counts_dict["hw.perflevel0.logicalcpu"]
    except:
        e_core_count = "?"
        p_core_count = "?"
    soc_info = {
        "name": cpu_info_dict["machdep.cpu.brand_string"],
        "core_count": int(cpu_info_dict["machdep.cpu.core_count"]),
        "cpu_max_power": None,
        "gpu_max_power": None,
        "e_core_count": e_core_count,
        "p_core_count": p_core_count,
        "gpu_core_count": get_gpu_cores()
    }
    # TDP (power)
    if soc_info["name"] == "Apple M1 Max":
        soc_info["cpu_max_power"] = 30
        soc_info["gpu_max_power"] = 60
    elif soc_info["name"] == "Apple M1 Pro":
        soc_info["cpu_max_power"] = 30
        soc_info["gpu_max_power"] = 30
    elif soc_info["name"] == "Apple M1":
        soc_info["cpu_max_power"] = 20
        soc_info["gpu_max_power"] = 20
    elif soc_info["name"] == "Apple M1 Ultra":
        soc_info["cpu_max_power"] = 60
        soc_info["gpu_max_power"] = 120
    elif soc_info["name"] == "Apple M2":
        soc_info["cpu_max_power"] = 25
        soc_info["gpu_max_power"] = 15
    elif soc_info["name"] == "Apple M2 Pro":
        soc_info["cpu_max_power"] = 30
        soc_info["gpu_max_power"] = 19
    elif soc_info["name"] == "Apple M2 Max":
        soc_info["cpu_max_power"] = 38
        soc_info["gpu_max_power"] = 38
    elif soc_info["name"] == "Apple M2 Ultra":
        soc_info["cpu_max_power"] = 76
        soc_info["gpu_max_power"] = 76
    elif soc_info["name"] == "Apple M3":
        soc_info["cpu_max_power"] = 22
        soc_info["gpu_max_power"] = 13
    elif soc_info["name"] == "Apple M3 Pro":
        soc_info["cpu_max_power"] = 37
        soc_info["gpu_max_power"] = 19
    elif soc_info["name"] == "Apple M3 Max":
        soc_info["cpu_max_power"] = 54
        soc_info["gpu_max_power"] = 47
    elif soc_info["name"] == "Apple M3 Ultra":
        soc_info["cpu_max_power"] = 108
        soc_info["gpu_max_power"] = 94
    elif soc_info["name"] == "Apple M4":
        soc_info["cpu_max_power"] = 22
        soc_info["gpu_max_power"] = 13
    elif soc_info["name"] == "Apple M4 Pro":
        soc_info["cpu_max_power"] = 42
        soc_info["gpu_max_power"] = 23
    elif soc_info["name"] == "Apple M4 Max":
        soc_info["cpu_max_power"] = 68
        soc_info["gpu_max_power"] = 57
    elif soc_info["name"] == "Apple M4 Ultra":
        soc_info["cpu_max_power"] = 136
        soc_info["gpu_max_power"] = 114
    else:
        soc_info["cpu_max_power"] = 20
        soc_info["gpu_max_power"] = 20
    return soc_info
