const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const files = [
    { name: 'student.html', out: 'redesign_student_1440.png' },
    { name: 'lecturer.html', out: 'redesign_lecturer_1440.png' },
    { name: 'hod.html', out: 'redesign_hod_1440.png' },
    { name: 'dean.html', out: 'redesign_dean_1440.png' },
    { name: 'admin.html', out: 'redesign_admin_1440.png' },
];

async function main() {
    const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
    console.log("Launching Chrome...");
    const chromeProc = spawn(chromePath, [
        "--headless=new",
        "--remote-debugging-port=9222",
        "--disable-extensions",
        "--disable-gpu",
        "--remote-allow-origins=*",
        "--window-size=1440,900",
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
    if (!pageTarget) throw new Error("No page target found");

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
        await sendCmd("Runtime.enable");

        await sendCmd("Emulation.setDeviceMetricsOverride", {
            width: 1440,
            height: 900,
            deviceScaleFactor: 1,
            mobile: false
        });

        for (const item of files) {
            const filePath = path.resolve(__dirname, item.name);
            const fileUrl = 'file:///' + filePath.replace(/\\/g, '/');
            console.log(`Testing ${item.name} at ${fileUrl}...`);
            await sendCmd("Page.navigate", { url: fileUrl });
            await new Promise(r => setTimeout(r, 800));

            const title = await sendCmd("Runtime.evaluate", { expression: "document.title", returnByValue: true });
            console.log(`Title for ${item.name}:`, title.result?.value);

            const scrollHeightRes = await sendCmd("Runtime.evaluate", {
                expression: "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, 900)",
                returnByValue: true
            });
            const height = Math.ceil(scrollHeightRes.result?.value || 900);

            await sendCmd("Emulation.setDeviceMetricsOverride", {
                width: 1440,
                height: height,
                deviceScaleFactor: 1,
                mobile: false
            });
            await new Promise(r => setTimeout(r, 300));

            const screenshot = await sendCmd("Page.captureScreenshot", {
                format: "png",
                clip: { x: 0, y: 0, width: 1440, height: height, scale: 1 }
            });

            const outPath = path.resolve(__dirname, 'document', item.out);
            fs.writeFileSync(outPath, Buffer.from(screenshot.data, "base64"));
            console.log(`Saved screenshot to: ${outPath}`);
        }

        console.log("All 5 files verified successfully!");
        ws.close();
    } finally {
        chromeProc.kill();
    }
}

main().catch(err => {
    console.error("Verification error:", err);
    process.exit(1);
});
