"""Paired experiment driver; each seed/share/flow reuses identical network+demand.

Try quick smoke: python run_batch.py --shares 0.1 0.7 --flows high --seeds 42
Full sweep: python run_batch.py --shares 0.1 0.3 0.5 0.7 0.8 --flows low medium high --seeds 1 2 ...
"""
import argparse
from dataclasses import replace
from config import Scenario, RESULTS
from build_network import generate_network
from generate_demand import generate_routes
from run_experiment import run_one
from metrics import write_dict_csv


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--shares',type=float,nargs='+',default=[.1,.4,.7])
    a.add_argument('--flows',nargs='+',choices=['low','medium','high'],default=['medium','high'])
    a.add_argument('--seeds',type=int,nargs='+',default=[42])
    a.add_argument('--only-p',nargs='+',choices=['P0','P1','P2','P3'],default=['P0','P1','P2','P3'])
    a.add_argument('--only-r',nargs='+',choices=['R0','R1','R2','R3'],default=['R0','R1','R2','R3'])
    a.add_argument('--ev-time',type=float,default=360.0)
    a.add_argument('--replay',action='store_true',help='Save large trajectory files (off by default)')
    args=a.parse_args()
    RESULTS.mkdir(parents=True,exist_ok=True)
    rows=[]
    base=Scenario()
    generate_network(base)
    for share in args.shares:
        for flow in args.flows:
            for seed in args.seeds:
                s=replace(base,two_wheeler_share=share,flow_level=flow,
                          seed=seed,ev_depart_s=args.ev_time)
                generate_routes(s)
                for p in args.only_p:
                    # P0 preemption-free baseline has no meaningful recovery variants.
                    recoveries=['R0'] if p=='P0' else args.only_r
                    for r in recoveries:
                        print(f'RUN share={share:.2f} flow={flow} seed={seed} {p}+{r}',flush=True)
                        try:
                            rows.append(run_one(s,p,r,replay=args.replay))
                            write_dict_csv(RESULTS/'batch_results.csv',rows)
                        except Exception as exc:
                            print('FAILED:',type(exc).__name__,str(exc),flush=True)
                            raise
    print('Saved',len(rows),'runs at',RESULTS/'batch_results.csv')

if __name__=='__main__':
    main()
