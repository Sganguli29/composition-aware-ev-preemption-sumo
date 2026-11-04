"""Analyze completed batch runs; paired EV-time differences and 95% CIs."""
import argparse
import math
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--csv',default='results/batch_results.csv')
    opts=parser.parse_args()
    df=pd.read_csv(opts.csv)
    out=Path(opts.csv).parent
    numeric=['ev_travel_s','mean_bg_proxy_delay_s','mean_two_wheeler_proxy_delay_s',
             'mean_other_proxy_delay_s','ev_stops','max_queue_vehicles']
    summary=df.groupby(['share','flow','p','r'],dropna=False)[numeric].agg(['mean','std','count'])
    summary.to_csv(out/'grouped_summary.csv')
    baseline=df[(df.p=='P0') & (df.r=='R0')][['share','flow','seed','ev_travel_s']].rename(
        columns={'ev_travel_s':'baseline_ev_s'})
    paired=df.merge(baseline,on=['share','flow','seed'],how='left')
    paired['ev_time_saved_s']=paired['baseline_ev_s']-paired['ev_travel_s']
    # Baseline-relative recovery: first 15-second sustained interval at or below
    # matched P0 queues + two vehicles, examined after the EV passes each signal.
    # Since a finite trace can end before recovery, that value is censored (NaN).
    for j in range(1, 6):
        paired[f'J{j}_recovery_to_p0_s'] = float('nan')
    base_lookup = { (row.share, row.flow, row.seed): row.tag
        for row in df[(df.p=='P0') & (df.r=='R0')].itertuples() }
    def recovery_delay(row, j):
        if row.p == 'P0':
            return 0.0
        passed = row.get(f'J{j}_pass_s')
        if pd.isna(passed):
            return float('nan')
        key = (row['share'], row['flow'], row['seed'])
        ref_tag = base_lookup.get(key)
        if not ref_tag:
            return float('nan')
        current = out/str(row['tag'])/'queue_series.csv'
        baseline = out/str(ref_tag)/'queue_series.csv'
        if not (current.exists() and baseline.exists()):
            return float('nan')
        c = pd.read_csv(current)
        b = pd.read_csv(baseline)
        col = f'J{j}_queue'
        x = c[['time_s',col]].merge(b[['time_s',col]],on='time_s',suffixes=('_actual','_p0'))
        x = x[x.time_s >= passed]
        # 15 seconds at step=0.2 seconds (round up for float jitter).
        span = max(1,round(15/0.2))
        ok = (x[col+'_actual'] <= x[col+'_p0'] + 2).to_numpy()
        for start in range(0,len(ok)-span+1):
            if ok[start:start+span].all():
                return max(0.0,float(x.iloc[start].time_s)-float(passed))
        return float('nan')
    for idx, row in paired.iterrows():
        for j in range(1,6):
            paired.at[idx,f'J{j}_recovery_to_p0_s']=recovery_delay(row,j)
    paired['mean_recovery_to_p0_s'] = paired[[f'J{j}_recovery_to_p0_s' for j in range(1,6)]].mean(axis=1)
    paired.to_csv(out/'paired_results.csv',index=False)
    groups=[]
    for keys,g in paired.groupby(['share','flow','p','r']):
        x=g['ev_time_saved_s'].dropna()
        n=len(x)
        std=x.std(ddof=1) if n>=2 else float('nan')
        mean=x.mean() if n else float('nan')
        half=1.96*std/math.sqrt(n) if n>=2 else float('nan')
        groups.append(dict(zip(['share','flow','p','r'],keys)) |
                      dict(n=n,mean_ev_saved_s=mean,std_ev_saved_s=std,
                           ci95_low=mean-half,ci95_high=mean+half))
    pd.DataFrame(groups).to_csv(out/'paired_ci95.csv',index=False)
    for flow,chunk in paired.groupby('flow'):
        fig,ax=plt.subplots(figsize=(9,5))
        for (p,r),v in chunk.groupby(['p','r']):
            if p=='P0' or (p!='P3' and r!='R0'):
                continue
            line=v.groupby('share')['ev_time_saved_s'].mean()
            ax.plot(line.index,line.values,marker='o',label=f'{p}+{r}')
        ax.set(xlabel='Two-wheeler share',ylabel='Mean EV seconds saved vs P0',
               title=f'EV time saved — {flow} demand')
        ax.legend()
        fig.tight_layout()
        fig.savefig(out/f'ev_saved_{flow}.png',dpi=170)
        plt.close(fig)
    for flow,chunk in paired.groupby('flow'):
        fig,ax=plt.subplots(figsize=(9,5))
        for (p,r),v in chunk.groupby(['p','r']):
            if (p,r) not in [('P1','R0'),('P2','R0'),('P3','R0'),('P3','R3')]:
                continue
            line=v.groupby('share')['mean_recovery_to_p0_s'].mean()
            ax.plot(line.index,line.values,marker='o',label=f'{p}+{r}')
        ax.set(xlabel='Two-wheeler share',ylabel='Mean recovery to matched P0 queue (s)',
               title=f'Queue recovery — {flow} demand')
        ax.legend()
        fig.tight_layout()
        fig.savefig(out/f'recovery_{flow}.png',dpi=170)
        plt.close(fig)
    print('Saved summary, paired differences, CIs and EV-saving/recovery charts to',out)
    print('Caution: reported background delay is a speed-deficit proxy, not true trip delay.')
    print('95% intervals use a normal approximation; use bootstrap or t CIs for small n.')

if __name__=='__main__':
    main()
