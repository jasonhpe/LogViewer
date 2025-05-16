import os
import re
import tarfile
import subprocess
import json
import shutil
from datetime import datetime, timezone

output_dir = "log_analysis_results"
fastlog_output_dir = os.path.join(output_dir, "fastlogs")
os.makedirs(output_dir, exist_ok=True)
os.makedirs(fastlog_output_dir, exist_ok=True)

patterns = [
    re.compile(r'(?P<timestamp>\d{4}-\d{2}-\d{2}T[\d:.+\-]+)\s+(?P<hostname>\S+)\s+(?P<process>[^\[:]+)(?:\[(?P<pid>\d+)\])?:\s+Event\|(?P<event_id>\d+)\|(?P<severity>\S+)\|(?P<module>\S+)\|(?P<slot>[^|]*)\|(?P<message>.+)'),
    re.compile(r'(?P<timestamp>\d{4}-\d{2}-\d{2}T[\d:.+\-]+)\s+(?P<hostname>\S+)\s+(?P<process>[^\[:]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<facility>\S+)\|(?P<severity>\S+)\|(?P<module>\S+)\|(?P<slot>[^|]*)\|(?P<submodule>[^|]*)\|(?P<source>[^|]*)\|(?P<message>.+)'),
    re.compile(r'(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+[\d:]{8})\s+(?P<hostname>\S+)\s+(?P<process>[^\[:]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<message>.+)')
]

def extract_bundle(path):
    tmp_dir = os.path.join(output_dir, "tmp", os.path.basename(path).replace(".tar.gz", ""))
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        with tarfile.open(path, "r:gz") as tar:
            tar.extractall(path=tmp_dir)
        return tmp_dir
    except Exception as e:
        print(f"❌ Failed to extract {path}: {e}")
        return None

def read_lines(path):
    if os.path.isdir(path):
        result = subprocess.run(["journalctl", "-D", path, "--no-pager"], stdout=subprocess.PIPE, text=True)
        return result.stdout.splitlines()
    else:
        with open(path, "r", errors='ignore') as f:
            return f.readlines()

def parse_line(line):
    for pattern in patterns:
        match = pattern.match(line.strip())
        if match:
            group = match.groupdict()
            try:
                if "T" in group["timestamp"]:
                    dt = datetime.fromisoformat(group["timestamp"])
                else:
                    dt = datetime.strptime(group["timestamp"], "%b %d %H:%M:%S").replace(year=datetime.now().year)
                group["timestamp"] = dt.astimezone(timezone.utc).isoformat()
            except Exception as e:
                print(f"⚠️ Failed to parse timestamp: {group.get('timestamp')} - {e}")
                return None
            return group
    return None

def collect_event_logs(bundle_dir):
    logs = []
    for root, _, files in os.walk(bundle_dir):
        for file in files:
            if file.endswith(".log") or "journal" in file:
                for line in read_lines(os.path.join(root, file)):
                    entry = parse_line(line)
                    if entry:
                        entry["source"] = "eventlog"
                        logs.append(entry)
    return logs

def collect_fastlogs(bundle_dir):
    fastlog_files = []
    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            if fname.endswith(".supportlog"):
                full_path = os.path.join(root, fname)
                try:
                    result = subprocess.run(["fastlogParser", "-v", full_path], stdout=subprocess.PIPE, text=True)
                    out_file = os.path.join(fastlog_output_dir, fname + ".txt")
                    with open(out_file, "w") as f:
                        f.write(result.stdout)
                    fastlog_files.append(fname + ".txt")
                except Exception as e:
                    print(f"⚠️ Failed to parse {fname}: {e}")
    return fastlog_files

def collect_fastlog_entries(bundle_dir):
    entries = []
    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            if fname.endswith(".supportlog"):
                full_path = os.path.join(root, fname)
                process_name = os.path.basename(fname).replace(".supportlog", "")
                try:
                    result = subprocess.run(["fastlogParser", "-v", full_path], stdout=subprocess.PIPE, text=True)
                    lines = result.stdout.splitlines()
                    buffer = []
                    timestamp = None
                    for line in lines:
                        if re.match(r"\(\d{2} \w{3} \d{2} \d{2}:\d{2}:\d{2}\.\d+", line):
                            if buffer and timestamp:
                                entries.append({
                                    "timestamp": timestamp,
                                    "process": process_name,
                                    "message": "\n".join(buffer),
                                    "source": "fastlog"
                                })
                            buffer = [line.strip()]
                            match = re.match(r"\((?P<ts>\d{2} \w{3} \d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
                            try:
                                raw_ts = match.group("ts")
                                truncated_ts = re.sub(r'\.(\d{6})\d+', r'.\1', raw_ts)
                                dt = datetime.strptime(truncated_ts, "%d %b %y %H:%M:%S.%f")
                                timestamp = dt.astimezone(timezone.utc).isoformat()
                            except Exception as e:
                                print(f"⚠️ Failed to parse fastlog timestamp in {fname}: {line.strip()} - {e}")
                                timestamp = None
                                buffer = []
                        else:
                            if buffer is not None:
                                buffer.append(line.strip())
                    if buffer and timestamp:
                        entries.append({
                            "timestamp": timestamp,
                            "process": process_name,
                            "message": "\n".join(buffer),
                            "source": "fastlog"
                        })
                except Exception as e:
                    print(f"⚠️ Failed to extract fastlog entries from {fname}: {e}")
    return entries

def collect_showtech_and_diag(bundle_dir):
    showtech = None
    diag = {}
    isp = None
    for root, _, files in os.walk(bundle_dir):
        for file in files:
            if file == "showtech.txt":
                showtech = os.path.join(root, file)
            elif file == "isp.txt":
                isp = os.path.join(root, file)
            elif file == "diagdump.txt" and "feature" in root:
                rel_dir = os.path.relpath(root, bundle_dir)
                diag[rel_dir] = os.path.join(root, file)
    return showtech, diag, isp

def split_showtech(showtech_path):
    sections = {}
    current = None
    buffer = []

    def flush():
        if current and buffer:
            fname = f"showtech_{current.replace(' ', '_').replace('/', '_')}.txt"
            with open(os.path.join(output_dir, fname), "w") as f:
                f.writelines(buffer)
            sections[current] = fname

    with open(showtech_path, "r", errors='ignore') as f:
        for line in f:
            match = re.search(r'Command\s*:\s*show (.+)', line)
            if match:
                flush()
                current = f"show {match.group(1).strip()}"
                buffer = [line]
            elif current:
                buffer.append(line)
    flush()
    return sections

def save_text_file_summary(input_path, out_path):
    try:
        with open(input_path, 'r', errors='ignore') as f:
            content = f.read()
        with open(out_path, 'w') as out:
            out.write(content)
    except Exception as e:
        print(f"❌ Failed to process {input_path}: {e}")

def parse_bundle(bundle_path, output_dir):
    bundle_dir = extract_bundle(bundle_path)
    if not bundle_dir:
        return None

    logs = collect_event_logs(bundle_dir)
    logs.extend(collect_fastlog_entries(bundle_dir))
    logs.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))

    fastlog_files = collect_fastlogs(bundle_dir)
    with open(os.path.join(output_dir, "parsed_logs.json"), "w") as f:
        json.dump(logs, f, indent=2)
    with open(os.path.join(output_dir, "fastlog_index.json"), "w") as f:
        json.dump(fastlog_files, f, indent=2)

    showtech_path, diag_dumps, isp_file = collect_showtech_and_diag(bundle_dir)
    if isp_file:
        shutil.copy(isp_file, os.path.join(output_dir, "isp.txt"))
    if showtech_path:
        index = split_showtech(showtech_path)
        with open(os.path.join(output_dir, "showtech_index.json"), "w") as f:
            json.dump(index, f, indent=2)
    for name, path in diag_dumps.items():
        out_name = name.replace(os.sep, "_") + "_diagdump.txt"
        save_text_file_summary(path, os.path.join(output_dir, out_name))
    with open(os.path.join(output_dir, "diag_index.json"), "w") as f:
        json.dump(list(diag_dumps.keys()), f, indent=2)

    return bundle_dir
