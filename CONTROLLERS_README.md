# Phase 1–2 prototype controllers and experiments

This package contains the working Phase 0 files plus the prototype preemption and recovery study. **Vehicle appearance changes can be made later.** SUMO 1.28.0 supports the options used here; `build_network.py` has the fix for the conflicting `--tls.cycle.time` argument.

## On Windows (your existing setup)

1. Extract this ZIP into a **new** folder, e.g. `C:\SUMO_Project\sumo_controllers`, then open Command Prompt **inside the folder containing `run_experiment.py`**.
2. Run `python -m pip install -r requirements.txt`.
3. Run one visual controller scenario:

```cmd
python run_experiment.py --gui --share 0.70 --flow high --seed 42 --p P3 --r R3
```

4. Compare the no-preemption baseline (same random demand):

```cmd
python run_experiment.py --gui --share 0.70 --flow high --seed 42 --p P0 --r R0
```

5. Run all meaningful combinations on one composition and seed (13 runs):

```cmd
python run_batch.py --shares 0.7 --flows high --seeds 42
```

6. Run several paired seeds and two-wheeler shares:

```cmd
python run_batch.py --shares 0.1 0.4 0.7 --flows low medium high --seeds 1 2 3 4 5
python analysis.py --csv results/batch_results.csv
```

For a final study use at least 20–30 paired seeds per scenario. A full factorial sweep can take a long time; do a small smoke test first. `run_batch.py` writes `results/batch_results.csv` incrementally. Each scenario gets its own `results/share_...` folder containing controller events, EV trace, queue series, tripinfo and summary. To enable large position and traffic-light replay logs for each batch trial, add `--replay`. `run_experiment.py` enables them by default.

**Key data files:** `results/latest_run.csv` (one interactive run); `results/batch_results.csv` (one row per batch run); `results/paired_results.csv`, `results/paired_ci95.csv`, `results/grouped_summary.csv` (analysis), `results/ev_saved_*.png`, `results/recovery_*.png`.

## Controller definitions

- **P0**: fixed-time signal control; no preemption.
- **P1**: trigger EV green within 170m and ETA ≤12 s.
- **P2**: assumed queue clearance `3 + 2*n/3` seconds, where n counts slow vehicles on the approach.
- **P3**: composition-weighted queue work `3 + sum(w_class)/3 * (1 + 0.65*f_bike² + 0.35*f_bike*f_lateral)` seconds. Default weights: bike 0.9, car 2.2, auto 1.7, bus 4.7 and truck 4.4. Triggers with ETA ≤ predicted clearance + 4 seconds.
- **R0**: restore the fixed-time program at its global-clock phase immediately after EV passage.
- **R1**: fixed 8-second recovery interval (including a 2-second all-red transition), then return to base.
- **R2**: bounded 5–24-second recovery proportional to cross-street queue count.
- **R3**: bounded 5–24-second recovery weighted by cross-street composition and two-wheeler share.

Preemption starts with a 2-second all-red changeover. After EV passage, R1–R3 also enforce 2 seconds all-red before a cross-street green taken from an existing SUMO phase, with only cross-street signal indices green. This is a **simulation simplification**; validate conflicts / pedestrian movements / minimum greens before any road-use claim.

## Important scientific limitations

- This is a **prototype**, not an empirically verified improvement. P3 + R3 has not been shown to beat the baselines.
- P3's seepage factor uses *lateral offset among queued bikes*, not measured passing flux; it is an observable proxy that should be calibrated to field measurements or observed trajectories.
- `mean_bg_proxy_delay_s` is an **accumulated free-speed-deficit proxy**, not SUMO's actual `timeLoss`; for publication-grade delay use the tripinfo `timeLoss` with appropriate censoring rules and analyze that measure instead.
- `Jx_clearance_s` tracks when vehicles initially queued ahead have left the incoming edge, not the full queue-discharge curve. It is right-censored if the simulation ends.
- `Jx_recovery_policy_s` is simply the programmed recovery length, not observed normalization. The analysis script also computes `Jx_recovery_to_p0_s` from paired P0 queue histories: first 15-second sustained interval at or below the P0 queue plus two vehicles, after EV passage. This heuristic requires baseline data and can be censored.
- Current implementation has one EV travelling **eastbound**, 5 junctions; no turning manoeuvres, side-street routing, stochastic demand feedback, dynamic offsets, or transit priority.
- The fixed-time restoration assumes time-zero signal plans have no offsets (consistent with the generated network). 
- The 95% confidence intervals use a normal approximation; replace with paired bootstrap/t intervals for publication if required.
- **Do not claim actual seepage, 90-second fixed cycles, queue-clearance failure, or statistically significant superiority without observing and validating corresponding outputs.**

## Recommended next validation

Run one P0, one P2+R0 and one P3+R3 at the same share/flow/seed. Verify each EV passes all five junctions, read controller-event timestamps, inspect `positions.csv` and EV traces, and check whether green masking creates route conflicts. Then scale the sample count.
