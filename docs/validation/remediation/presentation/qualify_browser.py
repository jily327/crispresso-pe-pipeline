"""Exercise a wheel install with the Playwright harness exported from its tested revision."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import urllib.request

SUITES = {
    "viewer": ("gui", "", 8765, "results.json"),
    "run": ("m11b", ".run", 8766, "run-results.json"),
    "practical": ("practical", ".practical", 8768, "practical-results.json"),
    "recovery": ("m11c", ".recovery", 8767, "recovery-results.json"),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Frozen source, env, dist and package.json")
    parser.add_argument("output", type=Path, help="New private directory for this selection")
    parser.add_argument("node_modules", type=Path)
    parser.add_argument("selection", choices=[*SUITES, "gate"])
    parser.add_argument("--audit-gate", type=Path)
    parser.add_argument("--test-source", type=Path, help="Committed test-harness checkout; runtime always imports the wheel")
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, mode=0o700)
    package = args.package.resolve()
    source = package / "source"
    meta = json.loads((package / "package.json").read_text())
    wheel = package / "dist" / meta["wheel"]["file"]
    assert digest(wheel) == meta["wheel"]["sha256"]
    python = package / "env/bin/python"
    harness = args.test_source.resolve() if args.test_source else source
    tests = harness / "tests"
    env = dict(os.environ, HOME=str(root/"home"), PATH=str(python.parent)+":"+os.environ["PATH"],
               PYTHONNOUSERSITE="1", MPLCONFIGDIR=str(root/"matplotlib"),
               M3_CORE_EXECUTABLE=str(python.parent/"peanalyzer-crispresso"),
               M31_RUNTIME_IMAGE="pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c",
               PLAYWRIGHT_CHROMIUM_EXECUTABLE=shutil.which("chromium"),
               PEANALYZER_E2E_JOB_TIMEOUT_MS="600000", PEANALYZER_E2E_ASSERT_TIMEOUT_MS="30000",
               M10_E2E_ROOT=str(root/"fixtures"), M11_SETUP_ROOT=str(root/"setup"),
               M10_E2E_EVIDENCE=str(root/"immutability.json"), M10_INTEGRATION="1", M10_RESULTS_DIR=str(root/"fixtures"),
               M11B_E2E_ROOT=str(root/"run-case"), M11C_E2E_ROOT=str(root/"recovery-case"),
               PRACTICAL_E2E_ROOT=str(root/"practical-case"), M11C_E2E_PYTHON=str(python),
               M11C_E2E_SERVER=str(tests/"m11c_e2e_server.py"))
    env.pop("PYTHONPATH", None)
    Path(env["HOME"]).mkdir(mode=0o700)
    def info(cmd):
        return subprocess.check_output(cmd, cwd=root,env=env,text=True).strip()
    installed = info([python,"-c","from pathlib import Path; import peanalyzer; print(Path(peanalyzer.__file__).resolve())"])
    assert Path(installed).is_relative_to(package/"env")
    commands = []
    def run(cmd, log, cwd=root):
        commands.append([str(x) for x in cmd])
        with (root/log).open("w") as stream:
            subprocess.run(cmd, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT,check=True)
    metadata = dict(**meta, installed_module=installed, selection=args.selection,
                    python=info([python,"--version"]),node=info(["node","--version"]),
                    chromium=info([env["PLAYWRIGHT_CHROMIUM_EXECUTABLE"],"--version"]),
                    platform=platform.platform(), backend_image=env["M31_RUNTIME_IMAGE"],
                    backend_local_image_identity=info(["docker","image","inspect","--format","{{.Id}}",env["M31_RUNTIME_IMAGE"]]),
                    commands=commands, status="INCOMPLETE")
    harness_files = sorted(tests.glob("*.py"))
    if args.selection in SUITES:
        _, conf, _, _ = SUITES[args.selection]
        frontend = harness/"frontend"
        suite_dir = "e2e"+("-"+args.selection if args.selection!="viewer" else "")
        harness_files += sorted((frontend/suite_dir).glob("*.ts"))
        harness_files += [frontend/f"playwright{conf}.config.ts",frontend/"playwright.config.ts"]
    metadata["harness_sha256"] = {str(f.relative_to(harness)):digest(f) for f in harness_files}
    try:
        if args.selection == "gate":
            assert args.audit_gate
            metadata["auditor_script_sha256"] = digest(args.audit_gate)
            (root/"results").mkdir()
            env.update(AUD=str(root),PYTHONPATH=str(tests))
            run([python,args.audit_gate],"gate.log")
        else:
            if args.selection == "viewer":
                run([python,"-m","pytest","-q","-s",str(tests/"test_gui_integration.py")],"fixtures.log")
            frontend = root/"frontend"
            shutil.copytree(harness/"frontend",frontend,ignore=shutil.ignore_patterns("node_modules","test-results"))
            (frontend/"node_modules").symlink_to(args.node_modules.resolve(),target_is_directory=True)
            server,conf,port,result=SUITES[args.selection]
            cmd=[str(python),str(tests/f"{server}_e2e_server.py")]
            commands.append(cmd)
            with (root/"server.log").open("w") as stream:
                proc=subprocess.Popen(cmd,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT)
                try:
                    for _ in range(7200):
                        if proc.poll() is not None:
                            raise RuntimeError(f"Server exited with status {proc.returncode}")
                        try:
                            req=urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/capabilities",
                                                       headers={"X-Viewer-Token":"e2e-local-token"})
                            with urllib.request.urlopen(req,timeout=1) as response:
                                if response.status==200:
                                    break
                        except OSError:
                            pass
                        time.sleep(.25)
                    else:
                        raise RuntimeError("Browser server readiness timeout")
                    cmd=[str(frontend/"node_modules/.bin/playwright"),"test","--config",f"playwright{conf}.config.ts",
                         "--output",str(root/"artifacts")]
                    try:
                        run(cmd,"browser.log",frontend)
                    finally:
                        result_path=frontend/"test-results"/result
                        if result_path.exists():
                            shutil.copyfile(result_path,root/"results.json")
                            metadata["playwright_stats"]=json.loads(result_path.read_text())["stats"]
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait(timeout=60)
        metadata["status"]="PASS"
    finally:
        fixture_exts=(".fastq.gz",".csv",".yaml",".xlsx")
        metadata["fixture_sha256"]={str(path.relative_to(root)):digest(path) for path in sorted(root.rglob("*"))
            if path.is_file() and str(path).endswith(fixture_exts) and
            ("inputs" in path.parts or (path.name.endswith(".xlsx") and path.parent.name in ("pe","nuclease")))}
        (root/"evidence.json").write_text(json.dumps(metadata,indent=2)+"\n")


if __name__=="__main__":
    main()
