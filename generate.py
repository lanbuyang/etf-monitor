"""
GitHub Actions 執行此腳本，產生 index.html 後推回 repo。
"""
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
    ("1301.TW",    "1301 台塑"),
]
KD_PERIOD      = 9
SELL_THRESHOLD = 80
BUY_THRESHOLD  = 30


def calc_kd(df, period=9):
    low_min  = df["Low"].rolling(period).min()
    high_max = df["High"].rolling(period).max()
    rsv = (df["Close"] - low_min) / (high_max - low_min) * 100
    k = pd.Series(index=df.index, dtype=float)
    d = pd.Series(index=df.index, dtype=float)
    k.iloc[0] = d.iloc[0] = 50.0
    for i in range(1, len(rsv)):
        if pd.notna(rsv.iloc[i]):
            k.iloc[i] = k.iloc[i-1] * (2/3) + rsv.iloc[i] * (1/3)
            d.iloc[i] = d.iloc[i-1] * (2/3) + k.iloc[i] * (1/3)
        else:
            k.iloc[i] = k.iloc[i-1]
            d.iloc[i] = d.iloc[i-1]
    return k, d


def this_month_k(k: pd.Series) -> pd.Series:
    today = datetime.now().date()
    idx = k.index
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    month_start = pd.Timestamp(today.year, today.month, 1)
    today_ts    = pd.Timestamp(today)
    return k[(idx >= month_start) & (idx < today_ts)]


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

            lk_adj, k_adj = None, None
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

            sig_k  = lk_adj if lk_adj is not None else lk
            sig_ks = k_adj  if k_adj  is not None else k
            had_sell = bool((this_month_k(sig_ks) > SELL_THRESHOLD).any())
            had_buy  = bool((this_month_k(sig_ks) < BUY_THRESHOLD).any())
            if sig_k > SELL_THRESHOLD:
                signal = "當月賣出觀望" if had_sell else "賣出"
            elif sig_k < BUY_THRESHOLD:
                signal = "當月買進觀望" if had_buy else "買進"
            else:
                signal = "觀望"

            rows.append((name, lk, lk_adj, ld, lc, signal))
        except Exception as e:
            print(f"  [{ticker}] 錯誤: {e}")
            rows.append((name, None, None, None, None, "錯誤"))
    return rows


def build_html(data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC+8")

    SIGNAL_STYLE = {
        "賣出":         ("🔴", "#ff6b6b", "#2d1b1b"),
        "買進":         ("🟢", "#69db7c", "#1b2d1e"),
        "觀望":         ("⚪", "#adb5bd", "#222"),
        "當月賣出觀望": ("🟡", "#ffd43b", "#2d2710"),
        "當月買進觀望": ("🟡", "#ffd43b", "#2d2710"),
        "資料不足":     ("❓", "#adb5bd", "#222"),
        "錯誤":         ("⚠️", "#ffa94d", "#2d2010"),
    }

    rows_html = ""
    for name, k, k_adj, d, close, signal in data:
        icon, color, bg = SIGNAL_STYLE.get(signal, ("", "#fff", "#222"))
        k_s     = f"{k:.2f}"     if k     is not None else "—"
        k_adj_s = f"{k_adj:.2f}" if k_adj is not None else "—"
        d_s     = f"{d:.2f}"     if d     is not None else "—"
        c_s     = f"{close:.2f}" if close is not None else "—"
        rows_html += f"""
        <tr style="background:{bg}">
          <td style="color:#e9ecef;font-weight:600">{name}</td>
          <td style="color:{color};font-weight:700">{k_s}</td>
          <td style="color:#a78bfa;font-size:13px">{k_adj_s}</td>
          <td style="color:#868e96">{d_s}</td>
          <td style="color:#e9ecef">{c_s}</td>
          <td style="color:{color};font-weight:700">{icon} {signal}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台股 ETF KD 監控</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    background: #141414; color: #e9ecef;
    display: flex; justify-content: center; align-items: flex-start;
    min-height: 100vh; padding: 40px 16px;
  }}
  .card {{
    background: #1e1e1e; border-radius: 16px; padding: 32px;
    width: 100%; max-width: 820px; box-shadow: 0 8px 32px rgba(0,0,0,.5);
  }}
  h1 {{ font-size: 22px; color: #74c7ec; margin-bottom: 6px; }}
  .subtitle {{ font-size: 13px; color: #555; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; border-radius: 10px; overflow: hidden; }}
  thead tr {{ background: #2a2a2a; }}
  th {{ padding: 12px 16px; text-align: left; font-size: 13px; color: #74c7ec;
        letter-spacing: .05em; font-weight: 600; }}
  td {{ padding: 14px 16px; font-size: 15px; border-bottom: 1px solid #2a2a2a; }}
  tr:last-child td {{ border-bottom: none; }}
  .legend {{
    display: flex; flex-wrap: wrap; gap: 16px;
    margin-top: 20px; font-size: 13px; color: #555;
  }}
  .legend span {{ display: flex; align-items: center; gap: 6px; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  .badge {{
    display: inline-block; margin-top: 20px; padding: 6px 14px;
    background: #2a2a2a; border-radius: 8px; font-size: 12px; color: #555;
  }}

  /* 訊號說明展開區塊 */
  .info-section {{
    margin-top: 24px;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    overflow: hidden;
  }}
  .info-toggle {{
    width: 100%; background: #2a2a2a; border: none; cursor: pointer;
    padding: 12px 16px; display: flex; justify-content: space-between;
    align-items: center; color: #74c7ec; font-size: 14px; font-weight: 600;
  }}
  .info-toggle:hover {{ background: #333; }}
  .info-toggle .arrow {{ transition: transform .25s; font-style: normal; }}
  .info-body {{
    display: none; padding: 20px; font-size: 13px; color: #adb5bd;
    line-height: 1.8;
  }}
  .info-body.open {{ display: block; }}
  .info-body h4 {{ color: #74c7ec; margin: 14px 0 6px; font-size: 13px; }}
  .info-body h4:first-child {{ margin-top: 0; }}
  .info-body code {{
    background: #2a2a2a; padding: 2px 6px; border-radius: 4px;
    font-family: monospace; font-size: 12px; color: #e9ecef;
  }}
  .info-body table {{
    width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px;
  }}
  .info-body th {{
    background: #252525; color: #74c7ec; padding: 8px 12px;
    text-align: left; font-size: 12px; letter-spacing: 0;
  }}
  .info-body td {{ padding: 8px 12px; border-bottom: 1px solid #2a2a2a; color: #adb5bd; }}
  .info-body tr:last-child td {{ border-bottom: none; }}
  .info-body blockquote {{
    border-left: 3px solid #74c7ec; margin: 10px 0;
    padding: 8px 14px; background: #1a2a2a; border-radius: 0 6px 6px 0;
    color: #74c7ec; font-size: 13px;
  }}
  .btn-row {{ display: flex; gap: 10px; align-items: center; margin-top: 20px; flex-wrap: wrap; }}
  .btn {{
    padding: 9px 20px; border-radius: 8px; font-weight: 600;
    font-size: 14px; cursor: pointer; border: none;
  }}
  .btn-primary {{ background: #74c7ec; color: #141414; }}
  .btn-primary:hover {{ background: #89dceb; }}
  .btn-primary:disabled {{ background: #2a2a2a; color: #555; cursor: not-allowed; }}
  #status-msg {{
    font-size: 13px; color: #74c7ec; display: none;
    align-items: center; gap: 8px;
  }}
  .spinner {{
    width: 14px; height: 14px; border: 2px solid #333;
    border-top-color: #74c7ec; border-radius: 50%;
    animation: spin .8s linear infinite;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>

<div class="card">
  <h1>台股 ETF KD 監控</h1>
  <p class="subtitle">更新時間：{now}　　每日台灣時間 14:30 自動更新</p>
  <table>
    <thead>
      <tr>
        <th>ETF</th>
        <th>K9 (原始)</th>
        <th style="color:#a78bfa">K9 (還原)</th>
        <th>D9</th>
        <th>收盤價</th>
        <th>訊號</th>
      </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>
  <div class="legend">
    <span><div class="dot" style="background:#ff6b6b"></div> K9 &gt; 80 賣出</span>
    <span><div class="dot" style="background:#69db7c"></div> K9 &lt; 30 買進</span>
    <span><div class="dot" style="background:#ffd43b"></div> 當月出現過訊號 → 觀望</span>
    <span><div class="dot" style="background:#555"></div> 觀望</span>
  </div>

  <!-- 訊號說明展開區塊 -->
  <div class="info-section">
    <button class="info-toggle" onclick="toggleInfo(this)">
      <span>📖 訊號邏輯說明</span>
      <span class="arrow">▼</span>
    </button>
    <div class="info-body">
      <h4>指標計算</h4>
      <code>RSV = (今日收盤 − 近9日最低) / (近9日最高 − 近9日最低) × 100</code><br><br>
      <code>K9 今日 = K9 昨日 × 2/3 + RSV 今日 × 1/3　（初始值 50）</code><br>
      <code>D9 今日 = D9 昨日 × 2/3 + K9 今日 × 1/3　（初始值 50）</code><br><br>
      訊號以 <strong style="color:#a78bfa">K9（還原權息）</strong> 為準；若還原資料取得失敗，退回原始 K9。

      <h4>基本訊號門檻</h4>
      <table>
        <thead><tr><th>K9（還原）</th><th>訊號</th></tr></thead>
        <tbody>
          <tr><td>&gt; 80</td><td>🔴 賣出</td></tr>
          <tr><td>&lt; 30</td><td>🟢 買進</td></tr>
          <tr><td>30 – 80</td><td>⚪ 觀望</td></tr>
        </tbody>
      </table>

      <h4>「當月觀望」修正</h4>
      <blockquote>
        若本月（月初至昨天）每日收盤的 K9 <strong>曾經超過 80</strong>，則當月賣出訊號改為觀望；
        <strong>曾經低於 30</strong>，則當月買進訊號改為觀望。<br>
        方向相反的訊號不受影響。
      </blockquote>
      <table>
        <thead><tr><th>今日 K9</th><th>本月曾出現同方向訊號？</th><th>最終顯示</th></tr></thead>
        <tbody>
          <tr><td>&gt; 80</td><td>本月曾 &gt; 80</td><td>🟡 當月賣出觀望</td></tr>
          <tr><td>&gt; 80</td><td>本月只有 &lt; 30（或無）</td><td>🔴 賣出</td></tr>
          <tr><td>&lt; 30</td><td>本月曾 &lt; 30</td><td>🟡 當月買進觀望</td></tr>
          <tr><td>&lt; 30</td><td>本月只有 &gt; 80（或無）</td><td>🟢 買進</td></tr>
          <tr><td>30 – 80</td><td>—</td><td>⚪ 觀望</td></tr>
        </tbody>
      </table>
      <span style="color:#555">
        同一個月內，每日收盤的 KD 只取第一次同方向突破訊號，避免重複進出；
        但方向反轉（如本月先出現賣出、後出現買進）視為新訊號，正常顯示。
      </span>
    </div>
  </div>

  <div class="btn-row">
    <button class="btn btn-primary" id="refresh-btn" onclick="triggerRefresh()">⚡ 立即更新資料</button>
    <span id="status-msg">
      <div class="spinner"></div>
      <span id="status-text">觸發中…</span>
    </span>
  </div>
  <p class="badge">由 GitHub Actions 自動產生 · 資料來源：Yahoo Finance</p>
</div>

<script>
// Cloudflare Worker URL（部署後填入）
const WORKER_URL = 'https://etf-monitor-dispatch.lanbuyang.workers.dev';

function showStatus(msg, spinning = true) {{
  const el = document.getElementById('status-msg');
  document.getElementById('status-text').textContent = msg;
  el.querySelector('.spinner').style.display = spinning ? 'block' : 'none';
  el.style.display = 'flex';
}}
function hideStatus() {{ document.getElementById('status-msg').style.display = 'none'; }}

async function triggerRefresh() {{
  const btn = document.getElementById('refresh-btn');
  btn.disabled = true;
  showStatus('觸發更新中…');

  try {{
    const res = await fetch(WORKER_URL, {{ method: 'POST' }});
    const json = await res.json().catch(() => ({{}}));

    if (json.ok) {{
      showStatus('✅ 更新中，約 1 分鐘後頁面自動重整…');
      pollAndReload();
    }} else {{
      showStatus(`❌ 錯誤 ${{res.status}}，請稍後再試`, false);
      btn.disabled = false;
    }}
  }} catch(e) {{
    showStatus('❌ 網路錯誤，請確認連線', false);
    btn.disabled = false;
  }}
}}

function toggleInfo(btn) {{
  const body  = btn.nextElementSibling;
  const arrow = btn.querySelector('.arrow');
  const open  = body.classList.toggle('open');
  arrow.style.transform = open ? 'rotate(180deg)' : '';
}}

async function pollAndReload() {{
  // 等 15 秒讓 Actions 啟動，再倒數顯示
  let secs = 60;
  await new Promise(r => setTimeout(r, 15000));
  const timer = setInterval(() => {{
    secs -= 1;
    if (secs > 0) {{
      showStatus(`⏳ 約 ${{secs}} 秒後完成…`);
    }} else {{
      clearInterval(timer);
      showStatus('✅ 完成！重新載入頁面…', false);
      setTimeout(() => location.reload(), 1000);
    }}
  }}, 1000);
}}
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("抓取資料中…")
    data = fetch_data()
    html = build_html(data)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html 已產生完成。")
