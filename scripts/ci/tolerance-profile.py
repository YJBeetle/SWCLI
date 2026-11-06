"""Resolve a single native CI profile before any private runtime access."""
import argparse
from pathlib import Path

BRANCH = "refs/heads/codex/docprops-tolerances"


def resolve_profile(event, ref, *, native_full=False, calibrate=False, accept=False):
    if calibrate or accept:
        if event != "workflow_dispatch" or ref != BRANCH:
            raise ValueError("tolerance profiles require a manual dispatch on codex/docprops-tolerances")
        if native_full or (calibrate and accept):
            raise ValueError("choose exactly one native profile; full/calibration/public modes are mutually exclusive")
        return "tolerances-calibration" if calibrate else "tolerances-public"
    if event == "workflow_dispatch":
        return "full" if native_full else "portable"
    if event == "push" and ref.startswith("refs/tags/v"):
        return "full"
    return "portable"


def flag(text):
    if text.lower() not in ("", "true", "false"):
        raise argparse.ArgumentTypeError("flags must be true or false")
    return text.lower() == "true"


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--event",required=True);p.add_argument("--ref",required=True)
    p.add_argument("--native-full",type=flag,default=False)
    p.add_argument("--calibrate",type=flag,default=False);p.add_argument("--accept",type=flag,default=False)
    p.add_argument("--github-output",type=Path)
    args=p.parse_args(argv)
    try:profile=resolve_profile(args.event,args.ref,native_full=args.native_full,calibrate=args.calibrate,accept=args.accept)
    except ValueError as exc:p.error(str(exc))
    if args.github_output:
        with args.github_output.open("a",encoding="utf-8") as stream:stream.write("profile="+profile+"\n")
    print(profile)


if __name__=="__main__":main()
