"""
Corrected test. The previous CV control was destroyed by dropped levels
(integer-mm rounding merges adjacent disparity steps -> doubled gaps -> outliers).

Robust formulation:  if z = fb/d with INTEGER d, then 1/z lies on a uniform grid.
Project each level onto that grid and measure how far it sits from the nearest
integer grid point.

  H1 structured light : residuals cluster tightly at 0
  H0 uniform-in-z     : residuals spread uniformly over [-0.5, 0.5], std = 0.2887

H0 is a real alternative and this statistic can land on it, so the test can fail.
Sanity floor: integer-mm rounding alone injects  0.5/(z^2 * step)  grid units.
"""
import numpy as np
import os
z = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'depth_lattice.npy'))
inv = 1.0/z

# least-squares fit of a uniform grid to 1/z: inv ~ a + step*n, n integer
step = np.median(np.diff(inv))
for _ in range(50):                       # alternate: assign n, refit
    n = np.round((inv - inv[0]) / step)
    A = np.vstack([np.ones_like(n), n]).T
    (a, step), *_ = np.linalg.lstsq(A, inv, rcond=None)
resid = (inv - (a + step*n)) / step       # in grid units

print("levels: %d   fitted grid step: %.6e 1/mm   f*b/dd = %.1f" % (z.size, step, 1/step))
print("grid index n spans %d..%d  (%d slots, %d occupied -> %.0f%% of the lattice seen)"
      % (n.min(), n.max(), n.max()-n.min()+1, z.size, 100*z.size/(n.max()-n.min()+1)))

print("\n--- residual from nearest integer disparity level (grid units) ---")
print("  observed std : %.4f" % resid.std())
print("  H0 (uniform-in-z) predicts : 0.2887")
print("  rounding-noise floor       : %.4f" % np.mean(0.5/(z**2*step)))
print("  max |residual|             : %.4f" % np.abs(resid).max())

# formal: is the observed spread consistent with H0?
from math import sqrt
sigma_H0 = 0.2887
print("\n  ratio observed/H0 : %.3f" % (resid.std()/sigma_H0))
verdict = "STRUCTURED LIGHT (integer disparity)" if resid.std() < 0.5*sigma_H0 else "H0 not rejected"
print("  VERDICT:", verdict)

# and the physical constants that fall out
fb = 1/step
print("\n--- recovered device geometry ---")
print("  f*b/dd            = %.0f px*mm" % fb)
print("  published (b=75, f=585, dd=1/8 px) = 351000   ratio = %.4f" % (fb/351000))
print("  implied baseline if f=585px, dd=1/8: b = %.2f mm" % (fb/(585*8)))
print("  disparity index at 1m / 4m: %.1f / %.1f" % (fb/1000, fb/4000))
