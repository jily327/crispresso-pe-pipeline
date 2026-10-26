"""Launch the local viewer with explicit, immutable workspace registrations."""
import argparse
from pathlib import Path
import secrets
import uvicorn
from peanalyzer.gui.app import create_app


def main():
    parser=argparse.ArgumentParser(description='Read-only verified PEAnalyzer result viewer')
    parser.add_argument('--workspace',action='append',default=[],metavar='PATH',help='Register an existing workspace; repeat for more choices')
    parser.add_argument('--setup-fastq',action='append',default=[],metavar='PATH',help='Register a paired-pool FASTQ input for setup')
    parser.add_argument('--setup-demux',action='append',default=[],metavar='PATH',help='Register an immutable verified M2 archive for setup')
    parser.add_argument('--setup-output-root',action='append',default=[],metavar='PATH',help='Register an existing parent for output proposals; never created or written')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    token=secrets.token_urlsafe(32)
    app=create_app([(None,Path(p)) for p in args.workspace],token=token,setup_files=args.setup_fastq,setup_archives=args.setup_demux,setup_output_roots=args.setup_output_root)
    if not (Path(__file__).parent/'static/index.html').is_file():
        parser.error('Built viewer assets are missing. Run npm ci && npm run build in frontend before packaging.')
    print(f'Open http://127.0.0.1:{args.port}/#{token}',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False)


if __name__=='__main__':
    main()
