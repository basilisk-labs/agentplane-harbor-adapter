from __future__ import annotations

# ruff: noqa: E501

EVALUATOR_SCRIPT = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


SOURCE_WHITELIST = {
    "main.tex",
    "input.tex",
    "synonyms.txt",
    "vm.js",
    "gates.txt",
}


def run(
    args: list[str],
    *,
    cwd: Path,
    timeout: int = 60,
    log_path: Path,
) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        output = proc.stdout or ""
        append_log(log_path, "$ " + " ".join(args) + "\n" + output)
        return proc.returncode, output
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        append_log(log_path, "$ " + " ".join(args) + f"\nTIMEOUT after {timeout}s\n" + output)
        return 124, output
    except OSError as exc:
        append_log(log_path, "$ " + " ".join(args) + f"\nOSERROR: {exc}\n")
        return 127, str(exc)


def append_log(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def read_text(path: Path, limit: int = 500_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def write_outputs(report: dict[str, object], artifact_dir: Path) -> int:
    report_path = artifact_dir / "evaluator-report.json"
    feedback_path = artifact_dir / "evaluator-feedback.txt"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        f"verdict: {report['verdict']}",
        f"task_type: {report['task_type']}",
        f"confidence: {report['confidence']}",
    ]
    for failure in report["failures"]:
        lines.append(f"FAIL: {failure}")
    for warning in report["warnings"]:
        lines.append(f"WARN: {warning}")
    for hint in report["repair_hints"]:
        lines.append(f"HINT: {hint}")
    for passed in report["passes"]:
        lines.append(f"PASS: {passed}")
    feedback_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return 0 if report["verdict"] in {"pass", "inconclusive"} else 1


def base_report(attempt: str, task_type: str) -> dict[str, object]:
    return {
        "attempt": attempt,
        "task_type": task_type,
        "verdict": "fail",
        "confidence": "low",
        "passes": [],
        "failures": [],
        "warnings": [],
        "repair_hints": [],
        "checks": {},
        "artifacts": {},
    }


def executor_gate(report: dict[str, object], artifact_dir: Path) -> bool:
    exit_path = artifact_dir / "executor-exit-code.txt"
    if not exit_path.exists():
        report["failures"].append("executor did not write an exit code")
        report["repair_hints"].append("ensure the runner command completes and records its exit code")
        return False
    exit_code = read_text(exit_path).strip()
    report["checks"]["executor_exit_code"] = exit_code
    if exit_code != "0":
        report["failures"].append(f"executor exited with code {exit_code}")
        report["repair_hints"].append("repair the executor failure before optimizing task output")
        executor_log = artifact_dir / "executor.log"
        if executor_log.exists():
            tail = read_text(executor_log)[-6000:]
            report["artifacts"]["executor_log_tail"] = tail
        return False
    report["passes"].append("executor exited successfully")
    return True


def detect_task_type(cwd: Path) -> str:
    if (cwd / "main.tex").exists() and (cwd / "input.tex").exists() and (cwd / "synonyms.txt").exists():
        return "overfull-hbox"
    if Path("/app/deps/illum1.pov").exists():
        return "build-pov-ray"
    if Path("/app/sim.c").exists() and Path("/app/gates.txt").exists():
        return "circuit-fibsqrt"
    if Path("/app/doomgeneric_mips").exists():
        return "make-mips-interpreter"
    return "generic"


def git_changed_files(cwd: Path, log_path: Path) -> list[str]:
    if not (cwd / ".git").exists():
        return []
    code, output = run(["git", "status", "--short"], cwd=cwd, timeout=20, log_path=log_path)
    if code != 0:
        return []
    files: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        files.append(line[3:].strip())
    return files


def evaluate_overfull(cwd: Path, artifact_dir: Path, attempt: str, log_path: Path) -> dict[str, object]:
    report = base_report(attempt, "overfull-hbox")
    if not executor_gate(report, artifact_dir):
        return report

    changed = git_changed_files(cwd, log_path)
    forbidden: list[str] = []
    if changed:
        source_changes = sorted(
            path for path in changed if Path(path).name in SOURCE_WHITELIST and not path.endswith(".pdf")
        )
        report["checks"]["changed_source_files"] = source_changes
        forbidden = [path for path in source_changes if Path(path).name != "input.tex"]
        if forbidden:
            report["failures"].append(
                "unexpected source changes outside input.tex: " + ", ".join(forbidden)
            )
            report["repair_hints"].append("preserve main.tex and synonyms.txt; make text-only fixes in input.tex")

    before_main = read_text(cwd / "main.tex")
    synonyms = read_text(cwd / "synonyms.txt")
    if not synonyms.strip():
        report["warnings"].append("synonyms.txt is empty or unreadable")
    if "\\input" not in before_main and "input.tex" not in before_main:
        report["warnings"].append("main.tex does not visibly include input.tex; verify task structure manually")

    code, output = run(
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        cwd=cwd,
        timeout=90,
        log_path=log_path,
    )
    report["checks"]["pdflatex_exit_code"] = code
    if code != 0:
        report["failures"].append(f"pdflatex exited with code {code}")
        report["artifacts"]["pdflatex_tail"] = output[-4000:]
        report["repair_hints"].append("produce a compiling LaTeX document before checking line overflow")
        return report

    main_log = read_text(cwd / "main.log")
    overfull = re.findall(r"Overfull \\\\hbox.*", main_log)
    underfull = re.findall(r"Underfull \\\\hbox.*", main_log)
    report["checks"]["overfull_hbox_count"] = len(overfull)
    report["checks"]["underfull_hbox_count"] = len(underfull)
    if overfull:
        report["failures"].append(f"main.log still contains {len(overfull)} Overfull hbox warning(s)")
        report["artifacts"]["overfull_lines"] = overfull[:20]
        report["repair_hints"].append(
            "replace long words or phrases in input.tex with allowed synonyms until Overfull hbox count is zero"
        )
        return report

    if forbidden:
        report["repair_hints"].append("revert source changes outside input.tex even though pdflatex passes")
        return report

    report["verdict"] = "pass"
    report["confidence"] = "medium"
    report["passes"].append("pdflatex completed without Overfull hbox warnings")
    return report


def evaluate_povray(cwd: Path, artifact_dir: Path, attempt: str, log_path: Path) -> dict[str, object]:
    report = base_report(attempt, "build-pov-ray")
    if not executor_gate(report, artifact_dir):
        return report

    povray = Path("/usr/local/bin/povray")
    if not povray.exists() or not os.access(povray, os.X_OK):
        report["failures"].append("/usr/local/bin/povray is missing or not executable")
        report["repair_hints"].append("build and install the real POV-Ray binary at /usr/local/bin/povray")
        return report

    code, version = run([str(povray), "-version"], cwd=cwd, timeout=20, log_path=log_path)
    report["checks"]["povray_version_exit_code"] = code
    report["artifacts"]["povray_version"] = version[:2000]
    if code != 0:
        report["failures"].append("povray -version does not run")
        report["repair_hints"].append("fix the installed binary rather than wrapping a failing command")
        return report
    if "Persistence of Vision" not in version and "POV-Ray" not in version:
        report["failures"].append("povray -version output does not identify POV-Ray")
        report["repair_hints"].append("install the actual POV-Ray executable, not a placeholder wrapper")
        return report

    binary_head = b""
    try:
        binary_head = povray.read_bytes()[:512]
    except OSError:
        pass
    if binary_head.startswith(b"#!"):
        text = binary_head.decode("utf-8", errors="replace")
        if "exec" not in text or "povray" not in text.lower():
            report["failures"].append("/usr/local/bin/povray looks like a thin non-exec wrapper")
            report["repair_hints"].append("the installed command should execute a real POV-Ray build")
            return report

    output = artifact_dir / f"povray-attempt-{attempt}.png"
    include_dir = "/app/povray-2.2/povdoc/include"
    scene = "/app/deps/illum1.pov"
    code, render_log = run(
        [
            str(povray),
            f"+L{include_dir}",
            f"+I{scene}",
            f"+O{output}",
            "+W64",
            "+H64",
            "+FN",
            "-D",
            "-P",
            "-V",
        ],
        cwd=cwd,
        timeout=120,
        log_path=log_path,
    )
    report["checks"]["povray_render_exit_code"] = code
    report["artifacts"]["povray_render_tail"] = render_log[-3000:]
    if code != 0 or not output.exists() or output.stat().st_size < 100:
        report["failures"].append("POV-Ray sanity render did not produce a non-empty PNG")
        report["repair_hints"].append("verify include paths, dependencies, and output format with illum1.pov")
        return report

    report["verdict"] = "pass"
    report["confidence"] = "medium"
    report["passes"].append("POV-Ray version and sanity render checks passed")
    report["artifacts"]["render_output"] = str(output)
    return report


def fib_mod(index: int) -> int:
    a, b = 0, 1
    for _ in range(index):
        a, b = b, (a + b) & 0xFFFFFFFF
    return a


def fibsqrt_oracle(value: int) -> int:
    return fib_mod(math.isqrt(value))


def evaluate_circuit(cwd: Path, artifact_dir: Path, attempt: str, log_path: Path) -> dict[str, object]:
    report = base_report(attempt, "circuit-fibsqrt")
    if not executor_gate(report, artifact_dir):
        return report

    sim = Path("/app/sim")
    if not sim.exists() or not os.access(sim, os.X_OK):
        code, output = run(["cc", "/app/sim.c", "-O2", "-o", "/app/sim"], cwd=cwd, timeout=60, log_path=log_path)
        report["checks"]["sim_compile_exit_code"] = code
        if code != 0:
            report["failures"].append("could not compile /app/sim.c")
            report["artifacts"]["compile_tail"] = output[-3000:]
            report["repair_hints"].append("repair gates.txt syntax so the public simulator can compile/run")
            return report

    cases = [0, 1, 2, 3, 4, 15, 16, 24, 25, 63, 64, 99, 100, 207, 208, 1024, 4096, 9999, 20000, 65535]
    failures: list[dict[str, object]] = []
    for value in cases:
        expected = str(fibsqrt_oracle(value))
        code, output = run(["/app/sim", str(value)], cwd=cwd, timeout=20, log_path=log_path)
        actual = output.strip().splitlines()[-1] if output.strip() else ""
        if code != 0 or actual != expected:
            failures.append({"input": value, "expected": expected, "actual": actual, "exit_code": code})
    report["checks"]["deterministic_case_count"] = len(cases)
    report["checks"]["failed_case_count"] = len(failures)
    if failures:
        report["failures"].append(f"gates.txt failed {len(failures)} deterministic fibsqrt case(s)")
        report["artifacts"]["failed_cases"] = failures[:20]
        report["repair_hints"].append(
            "derive gates from floor(sqrt(input)) followed by Fibonacci modulo 2^32; do not tune only two examples"
        )
        return report

    gates = read_text(Path("/app/gates.txt"))
    if len(gates.strip().splitlines()) < 3:
        report["warnings"].append("gates.txt is very short; hidden tests may reject an overfit circuit")

    report["verdict"] = "pass"
    report["confidence"] = "medium"
    report["passes"].append("gates.txt passed deterministic fibsqrt public oracle cases")
    return report


def evaluate_mips(cwd: Path, artifact_dir: Path, attempt: str, log_path: Path) -> dict[str, object]:
    report = base_report(attempt, "make-mips-interpreter")
    if not executor_gate(report, artifact_dir):
        return report

    vm = cwd / "vm.js"
    if not vm.exists():
        report["failures"].append("vm.js is missing")
        report["repair_hints"].append("create vm.js that loads /app/doomgeneric_mips and executes it")
        return report
    text = read_text(vm)
    signal_patterns = [
        r"doomgeneric_mips",
        r"readUInt(8|16|32)",
        r"DataView",
        r"syscall",
        r"\bregisters?\b|\bregs\b",
        r"\bopcode\b|\binstruction\b",
        r"\bpc\b|programCounter",
        r"\bELF\b|e_ident|program header",
        r"writeFileSync",
        r"\bmemory\b|ArrayBuffer|Uint8Array",
        r"\bhi\b|\blo\b",
        r"branch|jump|delay",
    ]
    signal_count = sum(1 for pattern in signal_patterns if re.search(pattern, text, flags=re.I))
    report["checks"]["static_interpreter_signal_count"] = signal_count
    if signal_count < 8:
        report["failures"].append("vm.js does not look like a real MIPS/ELF interpreter")
        report["repair_hints"].append(
            "implement ELF loading, CPU registers, instruction decode/execute, memory, syscalls, and BMP output"
        )
        return report
    if re.search(r"scaffold|stand[- ]?in|fake|placeholder|deterministic.*frame|gradient", text, flags=re.I):
        report["failures"].append("vm.js appears to be a scaffold or fake frame generator")
        report["repair_hints"].append("remove fabricated frame generation and execute doomgeneric_mips for real")
        return report

    code, output = run(["node", "vm.js"], cwd=cwd, timeout=60, log_path=log_path)
    frame_candidates = [Path("/tmp/frame.bmp"), *cwd.glob("**/*.bmp")]
    frames = [path for path in frame_candidates if path.exists() and path.is_file() and path.stat().st_size > 1000]
    report["checks"]["node_vm_exit_code"] = code
    report["checks"]["frame_candidate_count"] = len(frames)
    report["artifacts"]["node_vm_tail"] = output[-3000:]
    if not frames:
        report["failures"].append("node vm.js did not produce a plausible BMP frame")
        report["repair_hints"].append("run enough emulated execution to produce a real framebuffer BMP")
        return report

    report["verdict"] = "pass"
    report["confidence"] = "low"
    report["passes"].append("vm.js has interpreter signals and produced a BMP candidate")
    report["warnings"].append("MIPS local check is still weaker than the hidden verifier")
    report["artifacts"]["frame_candidates"] = [str(path) for path in frames[:10]]
    return report


def evaluate_generic(cwd: Path, artifact_dir: Path, attempt: str, log_path: Path) -> dict[str, object]:
    report = base_report(attempt, "generic")
    if not executor_gate(report, artifact_dir):
        return report
    report["verdict"] = "inconclusive"
    report["confidence"] = "low"
    report["passes"].append("executor exited successfully")
    report["warnings"].append("no task-specific public evaluator matched")
    report["repair_hints"].append("run the most relevant public task-local smoke check before final grading")
    return report


def main() -> int:
    # Public, task-local checks only. Do not read or run hidden graders in /tests.
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--artifact-dir", required=True)
    args = parser.parse_args()

    cwd = Path.cwd()
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifact_dir / f"evaluator-attempt-{args.attempt}.log"
    log_path.write_text("", encoding="utf-8")

    if shutil.which("timeout") is None:
        append_log(log_path, "WARN: timeout command is unavailable; Python subprocess timeouts remain active\n")

    task_type = detect_task_type(cwd)
    if task_type == "overfull-hbox":
        report = evaluate_overfull(cwd, artifact_dir, args.attempt, log_path)
    elif task_type == "build-pov-ray":
        report = evaluate_povray(cwd, artifact_dir, args.attempt, log_path)
    elif task_type == "circuit-fibsqrt":
        report = evaluate_circuit(cwd, artifact_dir, args.attempt, log_path)
    elif task_type == "make-mips-interpreter":
        report = evaluate_mips(cwd, artifact_dir, args.attempt, log_path)
    else:
        report = evaluate_generic(cwd, artifact_dir, args.attempt, log_path)

    report["checks"]["cwd"] = str(cwd)
    return write_outputs(report, artifact_dir)


if __name__ == "__main__":
    sys.exit(main())
'''
