import http.server
import threading
import webbrowser
import yfinance as yf
import pandas as pd
from datetime import datetime

ETFS = [
    ("0050.TW",    "0050 元大台灣50"),
    ("00757.TW",   "00757"),
    ("00631L.TW",  "00631L"),
    ("00662.TW",   "00662"),
    ("00864B.TWO", "00864B"),
    ("00719B.TWO", "00719B"),
    ("1301.TW",    "1301台塑"),
    ("1326.TW",    "1326台化"),
]
KD_PERIOD      = 9
SELL_THRESHOLD = 80
BUY_THRESHOLD  = 30
PORT           = 8899


def calc_kd(df, period=9):
    low_min = df["Low"].rolling(period).min()
    high_max = df["High"].rolling(period).max()
    rsv = (df["Close"] - low_min) / (high_max - low_min) * 100
    k = pd.Series(index=df.index, dtype=float)
    d = pd.Series(index=df.index, dtype=float)
    k.iloc[0] = d.iloc[0] = 50.0
    for i in range(1, len(rsv)):
        if pd.notna(rsv.iloc[i]):
            k.iloc[i] = k.iloc[i - 1] * (2 / 3) + rsv.iloc[i] * (1 / 3)
            d.iloc[i] = d.iloc[i - 1] * (2 / 3) + k.iloc[i] * (1 / 3)
        else:
            k.iloc[i] = k.iloc[i - 1]
            d.iloc[i] = d.iloc[i - 1]
    return k, d


def _this_month_k(k: pd.Series) -> pd.Series:
    today = datetime.now().date()
    idx = k.index
    # Strip timezone to avoid UTC-offset misclassifying Taiwan dates (e.g. May 1 → Apr 30 UTC)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    month_start = pd.Timestamp(today.year, today.month, 1)
    today_ts   = pd.Timestamp(today)
    return k[(idx >= month_start) & (idx < today_ts)]


def had_sell_this_month(k: pd.Series) -> bool:
    return bool((_this_month_k(k) > SELL_THRESHOLD).any())


def had_buy_this_month(k: pd.Series) -> bool:
    return bool((_this_month_k(k) < BUY_THRESHOLD).any())


def fetch_data():
    rows = []
    for ticker, name in ETFS:
        try:
            df = yf.download(ticker, period="3mo", interval="1d",
                             progress=False, auto_adjust=False)
            if df.empty or len(df) < KD_PERIOD:
                rows.append((name, None, None, None, None, "資料不足"))
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            k, d = calc_kd(df, KD_PERIOD)
            lk, ld, lc = k.iloc[-1], d.iloc[-1], df["Close"].iloc[-1]

            # 計算 auto_adjust=True 的 K9（還原權息），用於訊號判斷
            lk_adj = None
            k_adj  = None
            try:
                df_adj = yf.download(ticker, period="3mo", interval="1d",
                                     progress=False, auto_adjust=True)
                if not df_adj.empty and len(df_adj) >= KD_PERIOD:
                    if isinstance(df_adj.columns, pd.MultiIndex):
                        df_adj.columns = df_adj.columns.droplevel(1)
                    k_adj, _ = calc_kd(df_adj, KD_PERIOD)
                    lk_adj = k_adj.iloc[-1]
            except Exception:
                pass

            # 訊號以調整 K9 為準；若調整 K9 取得失敗則退回原始 K9
            sig_k  = lk_adj if lk_adj is not None else lk
            sig_ks = k_adj  if k_adj  is not None else k
            had_sell = had_sell_this_month(sig_ks)
            had_buy  = had_buy_this_month(sig_ks)
            if sig_k > SELL_THRESHOLD:
                signal = "當月賣出觀望" if had_sell else "賣出"
            elif sig_k < BUY_THRESHOLD:
                signal = "當月買進觀望" if had_buy else "買進"
            else:
                signal = "觀望"
            rows.append((name, lk, lk_adj, ld, lc, signal))
        except Exception:
            rows.append((name, None, None, None, None, "錯誤"))
    return rows


def build_html():
    data = fetch_data()
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    signal_style = {
        "賣出":   ("🔴", "#ff6b6b", "#2d1b1b"),
        "買進":   ("🟢", "#69db7c", "#1b2d1e"),
        "觀望":   ("⚪", "#adb5bd", "#222"),
        "當月賣出觀望": ("🟡", "#ffd43b", "#2d2710"),
        "當月買進觀望": ("🟡", "#ffd43b", "#2d2710"),
        "資料不足": ("❓", "#adb5bd", "#222"),
        "錯誤":   ("⚠️", "#ffa94d", "#2d2010"),
    }

    rows_html = ""
    for i, (name, k, k_adj, d, close, signal) in enumerate(data):
        icon, color, bg = signal_style.get(signal, ("", "#fff", "#222"))
        k_str     = f"{k:.2f}"     if k     is not None else "—"
        k_adj_str = f"{k_adj:.2f}" if k_adj is not None else "—"
        d_str     = f"{d:.2f}"     if d     is not None else "—"
        close_str = f"{close:.2f}" if close is not None else "—"
        rows_html += f"""
        <tr style="background:{bg}">
            <td style="color:#e9ecef;font-weight:600">{name}</td>
            <td style="color:{color};font-weight:700">{k_str}</td>
            <td style="color:#a78bfa;font-size:13px">{k_adj_str}</td>
            <td style="color:#868e96">{d_str}</td>
            <td style="color:#e9ecef">{close_str}</td>
            <td style="color:{color};font-weight:700">{icon} {signal}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="3600">
<title>台股 ETF KD 監控</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    background: #141414;
    color: #e9ecef;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    min-height: 100vh;
    padding: 40px 16px;
  }}
  .card {{
    background: #1e1e1e;
    border-radius: 16px;
    padding: 32px;
    width: 100%;
    max-width: 760px;
    box-shadow: 0 8px 32px rgba(0,0,0,.5);
  }}
  h1 {{
    font-size: 22px;
    color: #74c7ec;
    margin-bottom: 6px;
  }}
  .subtitle {{
    font-size: 13px;
    color: #555;
    margin-bottom: 24px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    border-radius: 10px;
    overflow: hidden;
  }}
  thead tr {{
    background: #2a2a2a;
  }}
  th {{
    padding: 12px 16px;
    text-align: left;
    font-size: 13px;
    color: #74c7ec;
    letter-spacing: .05em;
    font-weight: 600;
  }}
  td {{
    padding: 14px 16px;
    font-size: 15px;
    border-bottom: 1px solid #2a2a2a;
  }}
  tr:last-child td {{ border-bottom: none; }}
  .legend {{
    display: flex;
    gap: 20px;
    margin-top: 20px;
    font-size: 13px;
    color: #555;
  }}
  .legend span {{ display: flex; align-items: center; gap: 6px; }}
  .dot-sell {{ width:10px;height:10px;border-radius:50%;background:#ff6b6b; }}
  .dot-buy  {{ width:10px;height:10px;border-radius:50%;background:#69db7c; }}
  .dot-hold {{ width:10px;height:10px;border-radius:50%;background:#555; }}
  .dot-mhold{{ width:10px;height:10px;border-radius:50%;background:#ffd43b; }}
  .refresh-btn {{
    margin-top: 20px;
    display: inline-block;
    padding: 8px 20px;
    background: #74c7ec;
    color: #141414;
    border-radius: 8px;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    border: none;
    text-decoration: none;
  }}
  .refresh-btn:hover {{ background: #89dceb; }}
</style>
</head>
<body>
<div class="card">
  <h1>台股 ETF  KD 監控</h1>
  <p class="subtitle">更新時間：{now}　　頁面每小時自動刷新</p>
  <table>
    <thead>
      <tr>
        <th>ETF</th><th>K9</th><th style="color:#a78bfa">K9(調整)</th><th>D9</th><th>收盤價</th><th>訊號</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div class="legend">
    <span><div class="dot-sell"></div> K9 &gt; 80 賣出</span>
    <span><div class="dot-buy"></div> K9 &lt; 30 買進</span>
    <span><div class="dot-mhold"></div> 當月出現過訊號 → 當月賣出觀望 / 當月買進觀望</span>
    <span><div class="dot-hold"></div> 觀望</span>
  </div>
  <br>
  <a class="refresh-btn" href="/">立即更新</a>
</div>
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        html = build_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, *args):
        pass  # 關閉 console log


def open_browser(port):
    import subprocess, time
    time.sleep(1.5)
    subprocess.Popen(["open", f"http://127.0.0.1:{port}"])


def free_port(port):
    import subprocess
    result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
    pids = result.stdout.strip().split("\n")
    for pid in pids:
        if pid:
            subprocess.run(["kill", "-9", pid], capture_output=True)


def main():
    free_port(PORT)
    try:
        server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Port {PORT} 無法使用，請重試。")
        return
    url = f"http://127.0.0.1:{PORT}"
    print(f"ETF 監控已啟動：{url}")
    print("按 Ctrl+C 停止程式")
    threading.Thread(target=open_browser, args=(PORT,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
