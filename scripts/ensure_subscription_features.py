"""Register subscription features required by the deployment."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

NETWORK_NAMESPACE = "Microsoft.Network"
REQUIRED_FEATURES = ("AllowBringYourOwnPublicIpAddress",)


def az(*arguments: str) -> str:
    executable = shutil.which("az")
    if not executable:
        raise RuntimeError("Azure CLI is required")
    completed = subprocess.run(
        [executable, *arguments, "--only-show-errors", "--output", "tsv"],
        check=True,
        capture_output=True,
        text=True,
        shell=Path(executable).suffix.casefold() in {".cmd", ".bat"},
    )
    return completed.stdout.strip()


def ensure_feature(subscription_id: str, namespace: str, feature: str) -> None:
    state = az(
        "feature",
        "show",
        "--subscription",
        subscription_id,
        "--namespace",
        namespace,
        "--name",
        feature,
        "--query",
        "properties.state",
    )
    if state != "Registered":
        az(
            "feature",
            "register",
            "--subscription",
            subscription_id,
            "--namespace",
            namespace,
            "--name",
            feature,
        )
        for _ in range(60):
            state = az(
                "feature",
                "show",
                "--subscription",
                subscription_id,
                "--namespace",
                namespace,
                "--name",
                feature,
                "--query",
                "properties.state",
            )
            if state == "Registered":
                break
            time.sleep(10)
        else:
            raise RuntimeError(f"Timed out registering {namespace}/{feature}")
    print(f"PASS: {namespace}/{feature} is Registered")


def main() -> int:
    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID", "").strip()
    if not subscription_id:
        raise RuntimeError("AZURE_SUBSCRIPTION_ID is required")
    for feature in REQUIRED_FEATURES:
        ensure_feature(subscription_id, NETWORK_NAMESPACE, feature)
    az(
        "provider",
        "register",
        "--subscription",
        subscription_id,
        "--namespace",
        NETWORK_NAMESPACE,
        "--wait",
    )
    print(f"PASS: {NETWORK_NAMESPACE} registration is propagated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())