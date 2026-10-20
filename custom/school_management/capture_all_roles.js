const { spawn } = require('child_process');
const fs = require('fs');

async function main() {
    console.log("Authenticating admin user...");
    const authResp = await fetch("http://localhost:8070/web/session/authenticate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            jsonrpc: "2.0",
            params: {
                db: "odoo",
                login: "admin",
                password: "admin"
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
    console.log("Admin Session ID:", sessionId);

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

        console.log("Navigating to Executive Dashboard action-193 with menu_id=90...");
        await sendCmd("Page.navigate", { url: "http://localhost:8070/odoo?menu_id=90&action=193" });

        console.log("Waiting for Owl component to render...");
        await new Promise(r => setTimeout(r, 6000));

        const errDialog = await sendCmd("Runtime.evaluate", {
            expression: "document.querySelector('.o_error_dialog, .modal, .o_notification')?.innerText || 'NO_DIALOG'",
            returnByValue: true
        });
        console.log("Error dialog:", errDialog.result?.value);

        const hasSidebar = await sendCmd("Runtime.evaluate", {
            expression: "!!document.querySelector('.o_exec_sidebar')",
            returnByValue: true
        });
        console.log("Has executive sidebar element:", hasSidebar.result?.value);

        const sidebarInfo = await sendCmd("Runtime.evaluate", {
            expression: `
                const sidebar = document.querySelector('.o_exec_sidebar');
                if (!sidebar) return null;
                return {
                    width: sidebar.offsetWidth,
                    height: sidebar.offsetHeight,
                    navItemsCount: sidebar.querySelectorAll('.o_sidebar_nav_item').length,
                    profileName: sidebar.querySelector('.o_profile_name')?.innerText,
                    profileRole: sidebar.querySelector('.o_profile_role')?.innerText
                };
            `,
            returnByValue: true
        });
        console.log("Sidebar info:", sidebarInfo.result?.value);

        async function takeFullScreenshot(filename) {
            const scrollHeightRes = await sendCmd("Runtime.evaluate", {
                expression: `
                    Math.max(
                        document.body.scrollHeight,
                        document.documentElement.scrollHeight,
                        (document.querySelector('.o_executive_dashboard_container')?.scrollHeight || 0),
                        (document.querySelector('.o_student_mockup_dashboard')?.scrollHeight || 0),
                        1080
                    )
                `,
                returnByValue: true
            });
            const height = Math.ceil(scrollHeightRes.result?.value || 1080);
            const width = 1920;
            await sendCmd("Emulation.setDeviceMetricsOverride", {
                width: width,
                height: height,
                deviceScaleFactor: 1,
                mobile: false
            });
            await new Promise(r => setTimeout(r, 500));
            const screenshot = await sendCmd("Page.captureScreenshot", {
                format: "png",
                clip: { x: 0, y: 0, width: width, height: height, scale: 1 }
            });
            const outPath = `c:\\Odoo\\odoo\\custom\\school_management\\document\\${filename}`;
            fs.writeFileSync(outPath, Buffer.from(screenshot.data, "base64"));
            console.log(`Saved screenshot to: ${outPath}`);
        }

        // 1. Capture Admin Dashboard
        console.log("Capturing Admin Dashboard...");
        await takeFullScreenshot("admin_dashboard_fullpage.png");

        // 2. Collapse Sidebar and capture collapsed state
        console.log("Clicking sidebar collapse button...");
        await sendCmd("Runtime.evaluate", {
            expression: "document.querySelector('.o_btn_sidebar_toggle')?.click()",
            returnByValue: true
        });
        await new Promise(r => setTimeout(r, 600));
        await takeFullScreenshot("dashboard_sidebar_collapsed.png");

        // Expand sidebar back
        console.log("Restoring sidebar expanded state...");
        await sendCmd("Runtime.evaluate", {
            expression: "document.querySelector('.o_sidebar_header .cursor-pointer')?.click()",
            returnByValue: true
        });
        await new Promise(r => setTimeout(r, 600));

        // 3. Switch to HOD role view
        console.log("Switching to HOD role view...");
        await sendCmd("Runtime.evaluate", {
            expression: `
                const card = document.querySelector('.o_sidebar_profile_card');
                if (card) card.click();
            `,
            returnByValue: true
        });
        await new Promise(r => setTimeout(r, 400));
        await sendCmd("Runtime.evaluate", {
            expression: `
                const btns = Array.from(document.querySelectorAll('.o_profile_dropdown_menu button'));
                const hodBtn = btns.find(b => b.innerText.includes('Head of Dept'));
                if (hodBtn) hodBtn.click();
            `,
            returnByValue: true
        });
        await new Promise(r => setTimeout(r, 600));
        console.log("Capturing HOD Dashboard...");
        await takeFullScreenshot("hod_dashboard_fullpage.png");

        // 4. Switch to Dean role view
        console.log("Switching to Dean role view...");
        await sendCmd("Runtime.evaluate", {
            expression: `(() => {
                const card = document.querySelector('.o_sidebar_profile_card');
                if (card) card.click();
            })()`,
            returnByValue: true
        });
        await new Promise(r => setTimeout(r, 600));

        const clickDeanRes = await sendCmd("Runtime.evaluate", {
            expression: `(() => {
                const btns = Array.from(document.querySelectorAll('.o_profile_dropdown_menu button'));
                const deanBtn = btns.find(b => b.innerText && b.innerText.includes('Dean'));
                if (deanBtn) {
                    deanBtn.click();
                    return { found: true, text: deanBtn.innerText };
                }
                return { found: false, btns: btns.map(b => b.innerText) };
            })()`,
            returnByValue: true
        });
        console.log("Click Dean result:", clickDeanRes.result?.value);
        await new Promise(r => setTimeout(r, 1000));

        const currentProfile = await sendCmd("Runtime.evaluate", {
            expression: `(() => ({
                name: document.querySelector('.o_profile_name')?.innerText,
                role: document.querySelector('.o_profile_role')?.innerText
            }))()`,
            returnByValue: true
        });
        console.log("Current profile after switching to Dean:", currentProfile.result?.value);

        console.log("Capturing Dean Dashboard...");
        await takeFullScreenshot("dean_dashboard_fullpage.png");

        console.log("All role captures completed successfully!");
        ws.close();
    } finally {
        chromeProc.kill();
    }
}

main().catch(err => {
    console.error("Error in capture:", err);
    process.exit(1);
});
