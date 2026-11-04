"""Plan/register only this user's real-market local launchd daily agent."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.local.operation import LABEL,read_settings


def specification(directory):
    settings=read_settings(directory)
    return dict(Label=LABEL,ProgramArguments=[sys.executable,str(ROOT/'scripts/local_operation.py'),
        'daily','--data-dir',str(Path(directory).resolve())],WorkingDirectory=str(ROOT),
        StartCalendarInterval={'Hour':7,'Minute':30},RunAtLoad=True,
        EnvironmentVariables={'TZ':'Asia/Seoul','PATH':'/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'},
        StandardOutPath=str(Path(directory)/'logs'/'scheduler.log'),
        StandardErrorPath=str(Path(directory)/'logs'/'scheduler-error.log'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['plan','install','pause','resume','status','run'])
    p.add_argument('--data-dir',type=Path,required=True)
    a=p.parse_args();directory=a.data_dir.resolve();spec=specification(directory)
    target=Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
    domain=f'gui/{os.getuid()}';service=f'{domain}/{LABEL}'
    planned=directory/'daily-agent.plist';planned.write_bytes(plistlib.dumps(spec))
    if a.action=='plan':print(planned);return
    if a.action=='install':
        if target.exists() and plistlib.loads(target.read_bytes())!=spec:
            raise RuntimeError('Existing differently configured agent preserved; review before replacing.')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(planned.read_bytes())
        subprocess.run(['launchctl','bootstrap',domain,str(target)],check=True)
    elif a.action=='pause':subprocess.run(['launchctl','bootout',service],check=True)
    elif a.action=='resume':subprocess.run(['launchctl','bootstrap',domain,str(target)],check=True)
    elif a.action=='run':subprocess.run(['launchctl','kickstart',service],check=True)
    else:subprocess.run(['launchctl','print',service],check=True)
    print(f'{a.action}: {LABEL}; daily 07:30 in the Mac calendar timezone (this Mac is KST).')


if __name__=='__main__':main()
