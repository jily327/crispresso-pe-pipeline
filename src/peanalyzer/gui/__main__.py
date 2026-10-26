"""Launch the loopback GUI with server-owned input and runtime registrations."""
import argparse
from pathlib import Path
import secrets
import uvicorn
from peanalyzer.gui.app import create_app


def main():
    parser=argparse.ArgumentParser(description='Local PEAnalyzer setup, execution, and verified result viewer')
    parser.add_argument('--workspace',action='append',default=[],metavar='PATH',help='Register an existing workspace; repeat for more choices')
    parser.add_argument('--setup-fastq',action='append',default=[],metavar='PATH',help='Register a paired-pool FASTQ input for setup')
    parser.add_argument('--setup-demux',action='append',default=[],metavar='PATH',help='Register an immutable verified M2 archive for setup')
    parser.add_argument('--setup-output-root',action='append',default=[],metavar='PATH',help='Register an existing parent for new analyses; written only after explicit Run')
    parser.add_argument('--run-crispresso',default='CRISPResso',help='Server-owned local qualified CRISPResso executable; probed only after Run')
    parser.add_argument('--view-only',action='store_true',help='Disable Run while retaining setup and verified viewing')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    token=secrets.token_urlsafe(32)
    from peanalyzer.gui.execution import RuntimeSettings
    app=create_app([(None,Path(p)) for p in args.workspace],token=token,setup_files=args.setup_fastq,setup_archives=args.setup_demux,setup_output_roots=args.setup_output_root,runtime=None if args.view_only else RuntimeSettings(crispresso=args.run_crispresso))
    if not (Path(__file__).parent/'static/index.html').is_file():
        parser.error('Built viewer assets are missing. Run npm ci && npm run build in frontend before packaging.')
    print(f'Open http://127.0.0.1:{args.port}/#{token}',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False)


if __name__=='__main__':
    main()
