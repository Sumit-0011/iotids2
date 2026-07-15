"""
IoT IDS - Unified Launcher
===========================
Launch all components of the IoT Intrusion Detection System with a single command.
"""

import subprocess
import sys
import os
import signal
import time
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

BANNER = f"""
{Colors.CYAN}{Colors.BOLD}
  +----------------------------------------------------------+
  |          IoT Intrusion Detection System v2.0             |
  |     Adaptive Fuzzing Attack & ML-Based Defense           |
  +----------------------------------------------------------+
{Colors.RESET}"""

processes = []

def log(component, message, color=Colors.CYAN):
    print(f"  {color}[{component}]{Colors.RESET} {message}")

def start_process(name, script_path, color, delay=0):
    if delay:
        time.sleep(delay)
    
    full_path = os.path.join(BASE_DIR, script_path)
    if not os.path.exists(full_path):
        log(name, f"ERROR: {script_path} not found!", Colors.RED)
        return None
    
    log(name, f"Starting {script_path}...", color)
    
    proc = subprocess.Popen(
        [sys.executable, "-u", full_path],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append((name, proc, color))
    return proc

def cleanup(signum=None, frame=None):
    print(f"\n{Colors.YELLOW}{Colors.BOLD}  Shutting down all components...{Colors.RESET}")
    for name, proc, color in processes:
        if proc and proc.poll() is None:
            log(name, "Stopping...", color)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    log("SYSTEM", "All components stopped. Goodbye!", Colors.GREEN)
    sys.exit(0)

def _reader_thread(name, proc, color):
    """Read lines from a subprocess stdout in a dedicated thread."""
    try:
        for line in proc.stdout:
            line = line.strip()
            if line:
                log(name, line, color)
    except:
        pass

def stream_output():
    import threading as _threading
    
    # Spawn one reader thread per subprocess so readline() calls
    # never block each other (critical on Windows where select()
    # does not work on pipes).
    readers = []
    for name, proc, color in processes:
        t = _threading.Thread(target=_reader_thread, args=(name, proc, color), daemon=True)
        t.start()
        readers.append(t)
    
    # Wait until all subprocesses have exited.
    while any(proc.poll() is None for _, proc, _ in processes):
        time.sleep(0.5)

def main():
    parser = argparse.ArgumentParser(description="IoT IDS Unified Launcher")
    parser.add_argument("--attack", action="store_true")
    parser.add_argument("--smart-attack", action="store_true")
    parser.add_argument("--adversarial", action="store_true",
                        help="Live white-box adversarial bypass demo (IDS + dashboard + "
                             "adversarial attacker, simulator off)")
    parser.add_argument("--retrain", action="store_true")
    parser.add_argument("--train-ensemble", action="store_true",
                        help="Train the One-Class SVM second detector")
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--rule-based", action="store_true")
    parser.add_argument("--no-dashboard", action="store_true")
    parser.add_argument("--no-simulator", action="store_true")

    args = parser.parse_args()
    
    print(BANNER)
    
    if args.retrain:
        log("RETRAIN", "Starting adversarial retraining...", Colors.MAGENTA)
        result = subprocess.run([sys.executable, os.path.join(BASE_DIR, "training", "retrain.py")], cwd=BASE_DIR)
        sys.exit(result.returncode)

    if args.train_ensemble:
        log("ENSEMBLE", "Training One-Class SVM second detector...", Colors.MAGENTA)
        result = subprocess.run([sys.executable, os.path.join(BASE_DIR, "training", "train_ensemble.py")], cwd=BASE_DIR)
        sys.exit(result.returncode)
    
    if args.plot:
        log("PLOT", "Generating visualization...", Colors.MAGENTA)
        result = subprocess.run([sys.executable, os.path.join(BASE_DIR, "plots", "plot_graph.py")], cwd=BASE_DIR)
        sys.exit(result.returncode)
    
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    if not args.no_dashboard:
        start_process("DASHBOARD", os.path.join("dashboard", "app.py"), Colors.MAGENTA)
        time.sleep(1)
    
    if args.rule_based:
        start_process("IDS-RULE", os.path.join("server", "ids_rule.py"), Colors.GREEN)
    else:
        start_process("IDS-ML", os.path.join("server", "ids_ml.py"), Colors.GREEN)
    time.sleep(1)
    
    # In the adversarial bypass demo we want a PURE attack feed (no benign
    # simulator traffic) so the dashboard staying green is unambiguous proof.
    run_simulator = not args.no_simulator and not args.adversarial
    if run_simulator:
        start_process("SIMULATOR", os.path.join("simulator", "esp32_simulator.py"), Colors.CYAN, delay=1)

    if args.attack:
        start_process("ATTACKER", os.path.join("attacker", "adaptive_fuzzer.py"), Colors.RED, delay=3)
    elif args.smart_attack:
        start_process("ATTACKER", os.path.join("attacker", "smart_controller.py"), Colors.RED, delay=3)
    elif args.adversarial:
        start_process("ATTACKER", os.path.join("attacker", "adversarial_whitebox.py"), Colors.RED, delay=3)
    
    print()
    log("SYSTEM", f"{Colors.BOLD}All components running!{Colors.RESET}", Colors.GREEN)
    
    print(f"\n  {Colors.YELLOW}Press Ctrl+C to stop all components{Colors.RESET}\n")
    
    try:
        stream_output()
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
