# About COBALT

COBALT (**C**lick **O**rdering **B**inaural **A**daptive **L**ateralization **T**est) measures your temporal order judgment (TOJ) threshold — the smallest time gap between two sounds at which you can reliably tell which ear heard it first.

## How it works

Two sounds are played in rapid succession, one to each ear, with a gap of $\Delta t$ milliseconds. After each trial, you indicate which ear heard the sound first. The gap adapts using a **2-down 1-up staircase**, converging on the 70.7% correct threshold:

$$\hat{\theta} = \frac{1}{4}\sum_{i=3}^{6} r_i$$

where $r_i$ is the gap (in ms) at the $i$-th reversal.

## References

- Wetherill, G. B., & Levitt, H. (1965). Sequential estimation of points on a psychometric function. *British Journal of Mathematical and Statistical Psychology*, 18(1), 1–10.
