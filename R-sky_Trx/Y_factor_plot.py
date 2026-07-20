import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

CSV_PATH = Path("/home/sumikoshiko/Desktop/日付/ファイル名")
df = pd.read_csv(CSV_PATH)

bias_mv = df["bias_V"]*1000.0
current_ua = df["current_A"]*1e6
p_hot_dbm = df["P_hot_dBm"]
p_cold_dbm = df["P_cold_dBm"]
y_factor = df["Y_factor"]

# CSV内のLO周波数を取得してタイトルに使用
lo_freq = df["LO_freq_GHz"].iloc[0] if "LO_freq_GHz" in df.columns else 250.0

fig, ax1 = plt.subplots(figsize=(10, 5))
# 第1Y軸(左:Current[uA])
line_iv = ax1.plot(bias_mv, current_ua, color="c", label=f"IV(LO {lo_freq:.0f} GHz)")
ax1.set_xlabel("Bias Voltage (mV)", fontsize=16)
ax1.set_ylabel("Current (uA)", fontsize=16)
ax1.tick_params(axis="both", labelsize=16)
ax1.grid(True, linestyle="--", alpha=0.5)
# 0uAの参考破線
line_zero = ax1.axhline(0, color="black", linestyle="--", linewidth=1, label="IV")
# 第2Y軸(右第1:Power[dBm])
ax2 = ax1.twinx()
line_phot = ax2.plot(bias_mv, p_hot_dbm, color="r", label="P_hot")
line_pcold = ax2.plot(bias_mv, p_cold_dbm, color="b", label="P_cold")
ax2.set_ylabel("Power (dBm)", fontsize=16)
ax2.tick_params(axis="y", labelsize=16)
# 第3Y軸(右第2:Y-factor)
ax3 = ax1.twinx()
# 第3軸を右側に外挿(オフセット位置を指定)
ax3.spines["right"].set_position(("axes", 1.12))
line_y = ax3.plot(bias_mv, y_factor, color="g", label="Y-factor")
ax3.set_ylabel("Y-factor", fontsize=16)
ax3.tick_params(axis="y", labelsize=16)

plt.title(f"LO {lo_freq:.0f} GHz", fontsize=22, fontweight="bold", pad=15)

lines = [line_iv, line_phot, line_pcold, line_y, line_zero]
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc="upper left", frameon=True)
plt.subplots_adjust(right=0.82)  # 第3軸が入るスペースを確保
plt.tight_layout()
output_img = CSV_PATH.with_suffix(".png")
plt.savefig(output_img, dpi=300, bbox_inches="tight")
print(f"プロット画像を保存しました: {output_img}")
plt.show()