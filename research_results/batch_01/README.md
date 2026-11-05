\# Benchmark 01 — Initial Controller Comparison



\## Project



\*\*Does Two-Wheeler Seepage Break Queue-Clearance Preemption? Composition-Aware Emergency Vehicle Priority and Recovery in Heterogeneous Indian Traffic\*\*



\## Experiment Configuration



| Parameter | Value |

|---|---|

| Simulation | Eclipse SUMO 1.28.0 + Python TraCI |

| Network | Five signalized intersections |

| Lanes | Three per direction |

| Two-wheeler share | 70% |

| Traffic demand | High |

| Random seed | 42 |

| Ambulance departure | 360 simulation seconds |

| Simulation duration | 1,140 seconds |

| Controller combinations | 13 |



\## Controllers Evaluated



\*\*Preemption:\*\* P0 (fixed-time), P1 (simple priority), P2 (queue-clearance), P3 (composition-aware preemption).



\*\*Recovery:\*\* R0 (immediate restoration), R1 (fixed recovery), R2 (queue-proportional recovery), R3 (composition-aware recovery).



The experiment evaluates P0+R0 and all twelve combinations of P1–P3 with R0–R3.



\## Dataset



`batch\_results.csv` contains one row per completed simulation, including controller settings, emergency vehicle travel time, stops, background traffic delay proxies, queue measurements, and intersection-level observations.



\## Preliminary Findings



| Controller | EV travel time | EV stops |

|---|---:|---:|

| P0+R0 | 161.2 s | 3 |

| P2+R0 | 98.6 s | 0 |

| P3+R3 | 92.2 s | 0 |



The proposed P3+R3 configuration achieved a 42.8% reduction in ambulance travel time relative to fixed-time operation for this particular scenario.



However, P2+R0 and P3+R0 produced identical ambulance travel times. R2 and R3 also produced identical aggregate outcomes for the tested preemption strategies.



These findings do not yet establish independent or statistically significant improvements from the proposed algorithms.



\## Limitations



\- Only one random seed has been evaluated in this benchmark.

\- Background delay metrics are currently proxy measurements.

\- Actual post-preemption queue recovery has not been independently validated.

\- Motorcycle seepage requires quantitative trajectory-based verification.

\- SUMO reported emergency-braking and collision warnings in some runs.

\- Controller parameters are provisional and have not been calibrated using field observations.



\## Next Steps



1\. Diagnose P2/P3 and R2/R3 behavioural similarities.

2\. Validate signal transitions and collision events.

3\. Quantify motorcycle seepage.

4\. Evaluate additional traffic compositions and demand levels.

5\. Conduct multi-seed comparisons and statistical analysis.



\*\*Status:\*\* Preliminary simulation benchmark — not publication-validated results.

