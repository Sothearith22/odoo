const { spawn } = require('child_process');
const fs = require('fs');

async function main() {
    console.log("Authenticating student user...");
    const authResp = await fetch("http://localhost:8070/web/session/authenticate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            jsonrpc: "2.0",
            params: {
                db: "odoo",
                login: "student",
                password: "1234"
            }
        })
    });

    const setCookies = authResp.headers.getSetCookie ? authResp.headers.getSetCookie() : [authResp.headers.get('set-cookie')];
    let sessionId = null;
    for (const c of setCookies) {
        if (!c) continue;
        for (const part of c.split(';')) {
            if (part.trim().startsWith('session_id=')) {
                sessionId = part.trim().split('=')[1];
                break;
            }
        }
    }
    console.log("Session ID:", sessionId);

    const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
    console.log("Launching Chrome...");
    const chromeProc = spawn(chromePath, [
        "--headless=new",
        "--remote-debugging-port=9222",
        "--disable-extensions",
        "--disable-gpu",
        "--remote-allow-origins=*",
        "--window-size=1920,1080",
        "about:blank"
    ]);

    let pageTarget = null;
    for (let i = 0; i < 15; i++) {
        await new Promise(r => setTimeout(r, 600));
        try {
            const targetsRes = await fetch("http://localhost:9222/json");
            const targets = await targetsRes.json();
            pageTarget = targets.find(t => t.type === 'page' && !t.url.startsWith('chrome-extension'));
            if (pageTarget) break;
        } catch {}
    }
    if (!pageTarget) throw new Error("No page target found after retries");

    try {
        const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
        await new Promise((resolve, reject) => {
            ws.onopen = resolve;
            ws.onerror = reject;
        });

        let idCounter = 1;
        const pending = new Map();
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.method === 'Runtime.consoleAPICalled') {
                console.log('[BROWSER]', ...data.params.args.map(a => a.value || a.description));
            }
            if (data.method === 'Runtime.exceptionThrown') {
                console.error('[BROWSER ERROR]', data.params.exceptionDetails?.exception?.description || data.params.exceptionDetails?.text);
            }
            if (data.id && pending.has(data.id)) {
                const { resolve, reject } = pending.get(data.id);
                pending.delete(data.id);
                if (data.error) reject(data.error);
                else resolve(data.result);
            }
        };

        function sendCmd(method, params = {}) {
            const id = idCounter++;
            return new Promise((resolve, reject) => {
                pending.set(id, { resolve, reject });
                ws.send(JSON.stringify({ id, method, params }));
            });
        }

        await sendCmd("Page.enable");
        await sendCmd("Network.enable");
        await sendCmd("Runtime.enable");

        if (sessionId) {
            await sendCmd("Network.setCookie", {
                name: "session_id",
                value: sessionId,
                domain: "localhost",
                path: "/"
            });
        }

        console.log("Navigating to student dashboard action-198...");
        await sendCmd("Page.navigate", { url: "http://localhost:8070/odoo/action-198" });

        console.log("Waiting for Owl component to render...");
        await new Promise(r => setTimeout(r, 6000));

        const pageUrl = await sendCmd("Runtime.evaluate", { expression: "window.location.href", returnByValue: true });
        console.log("Current page URL:", pageUrl.result?.value);

        const pageTitle = await sendCmd("Runtime.evaluate", { expression: "document.title", returnByValue: true });
        console.log("Page title:", pageTitle.result?.value);

        const bodySnippet = await sendCmd("Runtime.evaluate", {
            expression: "document.body.innerText ? document.body.innerText.slice(0, 400) : 'EMPTY_BODY'",
            returnByValue: true
        });
        console.log("Body snippet:", bodySnippet.result?.value);

        const errDialog = await sendCmd("Runtime.evaluate", {
            expression: "document.querySelector('.o_error_dialog, .modal, .o_notification')?.innerText || 'NO_DIALOG'",
            returnByValue: true
        });
        console.log("Error dialog:", errDialog.result?.value);

        const hasDashboard = await sendCmd("Runtime.evaluate", { expression: "!!document.querySelector('.o_student_mockup_dashboard')", returnByValue: true });
        console.log("Has student dashboard mockup element:", hasDashboard.result?.value);

        const scrollHeightRes = await sendCmd("Runtime.evaluate", {
            expression: `
                Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight,
                    (document.querySelector('.o_student_mockup_dashboard')?.scrollHeight || 0) + 60,
                    1080
                )
            `,
            returnByValue: true
        });
        const height = Math.ceil(scrollHeightRes.result?.value || 1080);
        const width = 1920;
        console.log(`Setting device metrics override: ${width}x${height}`);

        await sendCmd("Emulation.setDeviceMetricsOverride", {
            width: width,
            height: height,
            deviceScaleFactor: 1,
            mobile: false
        });

        await new Promise(r => setTimeout(r, 600));

        const screenshot = await sendCmd("Page.captureScreenshot", {
            format: "png",
            clip: {
                x: 0,
                y: 0,
                width: width,
                height: height,
                scale: 1
            }
        });

        const outPath = "c:\\Odoo\\odoo\\custom\\school_management\\document\\student_dashboard_fullpage.png";
        fs.writeFileSync(outPath, Buffer.from(screenshot.data, "base64"));
        console.log("Saved full page screenshot to:", outPath);

        ws.close();
    } finally {
        chromeProc.kill();
    }
}

main().catch(err => {
    console.error("Error in capture:", err);
    process.exit(1);
});
