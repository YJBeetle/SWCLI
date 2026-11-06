"""One fresh public daemon/owned SW group; no calibration override or CAD retry."""
import argparse
import importlib.util
import os
import json
import socket
from pathlib import Path
from types import SimpleNamespace

spec=importlib.util.spec_from_file_location('_mates_public_runner',Path(__file__).with_name('verify-runtime-sets.py'))
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)


class PublicMateRunner(runtime.Runner):
    def preflight(self):
        # This dedicated job starts with no daemon. Windows may time out when
        # connecting to a vacant loopback port. Test binding instead, without
        # sending an RPC or attempting to shut down any other endpoint.
        address = (self.bind_host, self.bind_port)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(address)
        self.record["preflight_endpoint"] = {
            "host": self.bind_host,
            "port": self.bind_port,
            "bind_verified": True,
        }
        self.checkpoint()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--swconst',type=Path,required=True) # explicit installation identity, no COM calls
    args=parser.parse_args(argv)
    output=args.output_dir.resolve()
    from gate_support.package_identity import verify_installed_package
    output.mkdir(parents=True,exist_ok=True)
    package=verify_installed_package(Path(__file__).resolve().parents[2])
    with (output/'installed-package.json').open('x',encoding='utf-8') as stream:json.dump(package,stream,indent=2)
    os.environ['SWCLI_TRACE_NATIVE_CALLS']='1'
    options=SimpleNamespace(suite='core',mode='hidden',output_dir=output,host_output_dir=str(output),
        endpoint='127.0.0.1:18539',request_timeout=600,startup_timeout=600,set_timeout=1800,
        daemon_log=output/'daemon.log',fixture_work_dir=output/'private-fixture-work',
        host_fixture_work_dir=str(output/'private-fixture-work'),cli_command=None,python_path=[],
        sample_part='unused',sample_assembly='unused',sample_drawing='unused',sample_drawing_local=output/'unused',
        wine_prefix=None,drawing_template=None)
    runner=PublicMateRunner(options)
    from gate_support.runtime_plan import TestSet, Step
    runner.plan=(TestSet('assembly-mates',(Step('verify-assembly-mates.py','modeling'),)),)
    runner.record.update(expected_sets=['assembly-mates'],coverage_scope='public-assembly-standard-mates',
        session_policy='one-fresh-owned-host-no-intragroup-restart',full_acceptance_eligible=False,
        source_commit=os.environ.get('GITHUB_SHA'),internal_calibration=False)
    runner.checkpoint()
    try:runner.run()
    except BaseException as error:
        runner.record['error']=dict(type=type(error).__name__,message=str(error))
        runner.checkpoint()
        raise


if __name__=='__main__':main()
