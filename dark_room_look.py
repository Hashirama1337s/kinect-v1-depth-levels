"""Local preview of a dark_room capture (never published): depth median, temporal sigma, IR mean, raw-Bayer 2x2 block sum (stretched).
usage: python dark_room_look.py dark_room_dark.npz out.png"""
import sys
import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
z = np.load(sys.argv[1]); D = z['D'].astype(np.float64); D[D == 0] = np.nan
Zm = np.nanmedian(D, 0); sd = np.nanstd(D, 0); vf = np.mean(z['D'] > 0, 0)
I = z['I'].astype(np.float64).mean(0)
B = z['Bmean'].astype(np.float64); S = B[0::2, 0::2] + B[0::2, 1::2] + B[1::2, 0::2] + B[1::2, 1::2]
fig, ax = plt.subplots(2, 2, figsize=(13, 10))
im = ax[0, 0].imshow(Zm, cmap='turbo', vmin=np.nanpercentile(Zm, 2), vmax=np.nanpercentile(Zm, 98)); plt.colorbar(im, ax=ax[0, 0]); ax[0, 0].set_title('depth median (mm)')
im = ax[0, 1].imshow(np.where(vf > 0.5, sd, np.nan), cmap='magma', vmin=0, vmax=10); plt.colorbar(im, ax=ax[0, 1]); ax[0, 1].set_title('temporal sigma (mm), valid>50%')
im = ax[1, 0].imshow(np.log10(I + 1), cmap='gray'); ax[1, 0].set_title('IR mean (log)')
im = ax[1, 1].imshow(S, cmap='gray', vmin=np.percentile(S, 1), vmax=np.percentile(S, 99.5)); plt.colorbar(im, ax=ax[1, 1]); ax[1, 1].set_title('raw Bayer 2x2 sum (mean of frames)')
for a in ax.flat:
    a.set_xticks(range(0, 641, 80)); a.set_yticks(range(0, 481, 80)); a.grid(alpha=0.25)
plt.tight_layout(); plt.savefig(sys.argv[2], dpi=70)
