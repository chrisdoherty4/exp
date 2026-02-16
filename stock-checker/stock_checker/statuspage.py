import html
from dataclasses import dataclass, field
from datetime import datetime

from aiohttp import web

from stock_checker.checkers.base import StockStatus


@dataclass
class StoreStatus:
    store_type: str
    store_id: str
    product_id: str
    status: StockStatus = StockStatus.UNKNOWN
    last_checked: datetime | None = None


StatusBoard = dict[str, list[StoreStatus]]

STATUS_COLORS = {
    StockStatus.IN_STOCK: "#2e7d32",
    StockStatus.OUT_OF_STOCK: "#c62828",
    StockStatus.UNKNOWN: "#9e9e9e",
    StockStatus.ERROR: "#e65100",
}


def render_html(board: StatusBoard) -> str:
    parts = [
        "<!DOCTYPE html>",
        "<html><head>",
        '<meta charset="utf-8">',
        '<meta http-equiv="refresh" content="30">',
        "<title>Stock Checker Status</title>",
        "<style>",
        "body { font-family: sans-serif; margin: 2em; }",
        "table { border-collapse: collapse; margin-bottom: 2em; }",
        "th, td { border: 1px solid #ccc; padding: 0.5em 1em; text-align: left; }",
        "th { background: #f5f5f5; }",
        ".status { font-weight: bold; color: white; padding: 0.25em 0.75em; border-radius: 4px; }",
        "</style>",
        "</head><body>",
        "<h1>Stock Checker Status</h1>",
    ]

    if not board:
        parts.append("<p>No products configured.</p>")
    else:
        for product_name, statuses in board.items():
            parts.append(f"<h2>{html.escape(product_name)}</h2>")
            parts.append("<table>")
            parts.append(
                "<tr><th>Store</th><th>Store ID</th>"
                "<th>Product ID</th><th>Status</th><th>Last Checked</th></tr>"
            )
            for s in statuses:
                color = STATUS_COLORS.get(s.status, "#9e9e9e")
                checked = s.last_checked.strftime("%Y-%m-%d %H:%M:%S") if s.last_checked else "—"
                parts.append(
                    f"<tr>"
                    f"<td>{html.escape(s.store_type)}</td>"
                    f"<td>{html.escape(s.store_id)}</td>"
                    f"<td>{html.escape(s.product_id)}</td>"
                    f'<td><span class="status" style="background:{color}">'
                    f"{html.escape(s.status.value)}</span></td>"
                    f"<td>{checked}</td>"
                    f"</tr>"
                )
            parts.append("</table>")

    parts.append("</body></html>")
    return "\n".join(parts)


async def handle_index(request: web.Request) -> web.Response:
    board: StatusBoard = request.app["board"]
    return web.Response(text=render_html(board), content_type="text/html")


async def start_status_server(
    board: StatusBoard, host: str = "127.0.0.1", port: int = 8080
) -> web.AppRunner:
    app = web.Application()
    app["board"] = board
    app.router.add_get("/", handle_index)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner
