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
    ("1326.TW",    "1326 台化"),
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
            had_signal = (
                bool((this_month_k(sig_ks) > SELL_THRESHOLD).any()) or
                bool((this_month_k(sig_ks) < BUY_THRESHOLD).any())
            )
            if sig_k > SELL_THRESHOLD:
                signal = "當月賣出觀望" if had_signal else "賣出"
            elif sig_k < BUY_THRESHOLD:
                signal = "當月買進觀望" if had_signal else "買進"
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
  .btn-row {{ display: flex; gap: 10px; align-items: center; margin-top: 20px; flex-wrap: wrap; }}
  .btn {{
    padding: 9px 20px; border-radius: 8px; font-weight: 600;
    font-size: 14px; cursor: pointer; border: none;
  }}
  .btn-primary {{ background: #74c7ec; color: #141414; }}
  .btn-primary:hover {{ background: #89dceb; }}
  .btn-primary:disabled {{ background: #2a2a2a; color: #555; cursor: not-allowed; }}
  .btn-ghost {{ background: transparent; color: #555; border: 1px solid #333; font-size: 12px; }}
  .btn-ghost:hover {{ color: #888; border-color: #555; }}
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

  /* Token dialog */
  #token-dialog {{
    display: none; position: fixed; inset: 0;
    background: rgba(0,0,0,.7); z-index: 100;
    justify-content: center; align-items: center;
  }}
  #token-dialog.open {{ display: flex; }}
  .dialog-box {{
    background: #1e1e1e; border-radius: 14px; padding: 28px;
    width: min(420px, 90vw); box-shadow: 0 8px 40px rgba(0,0,0,.6);
  }}
  .dialog-box h3 {{ color: #74c7ec; margin-bottom: 10px; font-size: 16px; }}
  .dialog-box p {{ font-size: 13px; color: #888; margin-bottom: 14px; line-height: 1.6; }}
  .dialog-box a {{ color: #74c7ec; }}
  .dialog-box input {{
    width: 100%; padding: 9px 12px; background: #2a2a2a;
    border: 1px solid #444; border-radius: 8px; color: #e9ecef;
    font-size: 14px; margin-bottom: 14px; outline: none;
  }}
  .dialog-box input:focus {{ border-color: #74c7ec; }}
  .dialog-actions {{ display: flex; gap: 10px; justify-content: flex-end; }}
</style>
</head>
<body>

<!-- Token 輸入對話框 -->
<div id="token-dialog">
  <div class="dialog-box">
    <h3 id="dialog-title">🔑 輸入 GitHub Token</h3>
    <p id="dialog-desc">
      需要 <strong>GitHub Classic PAT</strong>（Personal Access Token）才能觸發 Actions 更新。<br>
      ⚠️ 請勿使用 Fine-grained token，必須使用 <strong>Classic</strong> 類型。<br><br>
      建立步驟：<br>
      1. 點下方連結 → 登入 GitHub<br>
      2. 確認已勾選 <strong>workflow</strong> 權限<br>
      3. 點「Generate token」→ 複製貼入下方<br><br>
      <a href="https://github.com/settings/tokens/new?scopes=workflow&description=ETF+Monitor" target="_blank">
        → 點此建立 Classic PAT（已預選 workflow 權限）
      </a><br><br>
      Token 僅存在本機瀏覽器，不會上傳。
    </p>
    <input type="password" id="token-input" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx" />
    <div class="dialog-actions">
      <button class="btn btn-ghost" onclick="closeDialog()">取消</button>
      <button class="btn btn-primary" onclick="saveToken()">儲存並更新</button>
    </div>
  </div>
</div>

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

  <div class="btn-row">
    <button class="btn btn-primary" id="refresh-btn" onclick="triggerRefresh()">⚡ 立即更新資料</button>
    <button class="btn btn-ghost" onclick="clearToken()" title="清除已儲存的 Token">🔑 清除 Token</button>
    <span id="status-msg">
      <div class="spinner"></div>
      <span id="status-text">觸發中…</span>
    </span>
  </div>
  <p class="badge">由 GitHub Actions 自動產生 · 資料來源：Yahoo Finance</p>
</div>

<script>
const OWNER    = 'lanbuyang';
const REPO     = 'etf-monitor';
const WORKFLOW = 'update.yml';
const LS_KEY   = 'etf_gh_token';

function getToken() {{ return localStorage.getItem(LS_KEY); }}
function closeDialog() {{ document.getElementById('token-dialog').classList.remove('open'); }}
function openDialog(msg) {{
  if (msg) document.getElementById('dialog-desc').innerHTML = msg +
    '<br><br><a href="https://github.com/settings/tokens/new?scopes=workflow&description=ETF+Monitor" target="_blank">→ 點此建立 Classic PAT</a>';
  document.getElementById('token-input').value = '';
  document.getElementById('token-dialog').classList.add('open');
}}
function clearToken() {{
  localStorage.removeItem(LS_KEY);
  showStatus('已清除 Token', false);
  setTimeout(() => hideStatus(), 2500);
}}

function saveToken() {{
  const t = document.getElementById('token-input').value.trim();
  if (!t) return;
  localStorage.setItem(LS_KEY, t);
  closeDialog();
  doTrigger(t);
}}

function showStatus(msg, spinning = true) {{
  const el = document.getElementById('status-msg');
  document.getElementById('status-text').textContent = msg;
  el.querySelector('.spinner').style.display = spinning ? 'block' : 'none';
  el.style.display = 'flex';
}}
function hideStatus() {{ document.getElementById('status-msg').style.display = 'none'; }}

async function triggerRefresh() {{
  const token = getToken();
  if (!token) {{
    document.getElementById('token-dialog').classList.add('open');
    return;
  }}
  doTrigger(token);
}}

async function doTrigger(token) {{
  const btn = document.getElementById('refresh-btn');
  btn.disabled = true;
  showStatus('觸發 GitHub Actions…');

  try {{
    const res = await fetch(
      `https://api.github.com/repos/${{OWNER}}/${{REPO}}/actions/workflows/${{WORKFLOW}}/dispatches`,
      {{
        method: 'POST',
        headers: {{
          Authorization: `Bearer ${{token}}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
        }},
        body: JSON.stringify({{ ref: 'main' }}),
      }}
    );

    if (res.status === 204) {{
      showStatus('✅ 更新中，約 1 分鐘後頁面自動重整…');
      pollAndReload(token);
    }} else if (res.status === 401) {{
      localStorage.removeItem(LS_KEY);
      showStatus('❌ Token 無效或已過期，請重新輸入', false);
      btn.disabled = false;
      setTimeout(() => {{ hideStatus(); openDialog('Token 無效或已過期，請重新建立。'); }}, 1500);
    }} else if (res.status === 403) {{
      localStorage.removeItem(LS_KEY);
      showStatus('❌ 權限不足（403）：Token 缺少 workflow 權限', false);
      btn.disabled = false;
      setTimeout(() => {{
        hideStatus();
        openDialog('⚠️ 權限不足（403 錯誤）<br><br>請確認：<br>・使用 <strong>Classic PAT</strong>（非 Fine-grained）<br>・建立時有勾選 <strong>workflow</strong> 權限<br><br>請重新建立 Token 後再試。');
      }}, 1500);
    }} else {{
      showStatus(`❌ 錯誤 ${{res.status}}，請稍後再試`, false);
      btn.disabled = false;
    }}
  }} catch(e) {{
    showStatus('❌ 網路錯誤，請確認連線', false);
    btn.disabled = false;
  }}
}}

async function pollAndReload(token) {{
  // 等 10 秒讓 Actions 排入佇列，再開始輪詢
  await new Promise(r => setTimeout(r, 10000));

  for (let i = 0; i < 20; i++) {{
    try {{
      const res = await fetch(
        `https://api.github.com/repos/${{OWNER}}/${{REPO}}/actions/runs?per_page=1&event=workflow_dispatch`,
        {{ headers: {{ Authorization: `Bearer ${{token}}`, Accept: 'application/vnd.github+json' }} }}
      );
      const json = await res.json();
      const run  = json.workflow_runs?.[0];
      if (run) {{
        const secs = Math.round((Date.now() - new Date(run.created_at)) / 1000);
        showStatus(`⏳ Actions 執行中（${{secs}}s）…`);
        if (run.status === 'completed') {{
          showStatus('✅ 完成！重新載入頁面…');
          setTimeout(() => location.reload(), 1500);
          return;
        }}
      }}
    }} catch(_) {{}}
    await new Promise(r => setTimeout(r, 6000));
  }}
  // 逾時仍重載
  showStatus('重新載入頁面…', false);
  setTimeout(() => location.reload(), 1000);
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
