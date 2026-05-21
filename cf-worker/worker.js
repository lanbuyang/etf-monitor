/**
 * Cloudflare Worker — ETF Monitor Dispatch Proxy
 *
 * 環境變數（在 Cloudflare Dashboard 設定）：
 *   GH_TOKEN   : GitHub Classic PAT（只需 workflow scope）
 *   GH_OWNER   : lanbuyang
 *   GH_REPO    : etf-monitor
 *   GH_WORKFLOW: update.yml
 */

const ALLOWED_ORIGIN = "https://lanbuyang.github.io";

export default {
  async fetch(request, env) {
    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: corsHeaders(ALLOWED_ORIGIN),
      });
    }

    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    // 呼叫 GitHub API 觸發 workflow_dispatch
    const url = `https://api.github.com/repos/${env.GH_OWNER}/${env.GH_REPO}/actions/workflows/${env.GH_WORKFLOW}/dispatches`;

    const res = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "etf-monitor-worker",
      },
      body: JSON.stringify({ ref: "main" }),
    });

    if (res.status === 204) {
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json", ...corsHeaders(ALLOWED_ORIGIN) },
      });
    }

    const text = await res.text();
    return new Response(JSON.stringify({ ok: false, status: res.status, body: text }), {
      status: res.status,
      headers: { "Content-Type": "application/json", ...corsHeaders(ALLOWED_ORIGIN) },
    });
  },
};

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}
